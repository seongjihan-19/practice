import os
import sys
import time

import numpy as np
from google.genai import types

from config import make_client

DOCS_DIR = "docs"
EXCLUDE = {"positioning_map.md", "유저 플로우.md", "MEJ_OEM_견적비교표.md"}  # 색인에서 뺀 3개
CHUNK_SIZE = 800  # 조각 크기 (글자)
OVERLAP = 150  # 조각 사이 겹침 (글자)
DIM = 768  # 임베딩 차원 (gemini-embedding-2 권장값, 자동 정규화)
BATCH = 50  # 임베딩 요청 1번에 보낼 조각 수
PER_MINUTE = 100  # 무료 등급 임베딩 한도 (분당 입력 100개)
TOP_K = 5  # 검색해서 답변에 넣을 조각 수
INDEX_PATH = "rag_index.npz"

SYSTEM_PROMPT = (
    "너는 문서 기반 질의응답 도우미다. 아래 [문서 조각]에 있는 내용만 근거로 한국어로 답한다. "
    "조각에 없는 내용은 추측하거나 계산해서 만들지 말고 '제공된 문서에는 답이 없습니다.'라고 답한다. "
    "답의 끝에 근거로 쓴 조각의 출처(docs/파일명)를 적는다."
)

client, GEN_MODEL = make_client("RAG")  # 답변 생성용 클라이언트·모델
EMBED_MODEL = os.environ["RAG_EMBED_MODEL"]  # 임베딩 모델


def split_text(text):
    """글을 CHUNK_SIZE 글자씩, OVERLAP 글자씩 겹치게 자른다."""
    step = CHUNK_SIZE - OVERLAP
    return [text[i:i + CHUNK_SIZE] for i in range(0, max(len(text) - OVERLAP, 1), step)]


def load_chunks():
    """docs/의 문서(제외 3개 빼고)를 조각내고, 조각과 출처('docs/파일명') 목록을 반환한다."""
    texts, sources = [], []
    for name in sorted(os.listdir(DOCS_DIR)):
        if not name.endswith(".md") or name in EXCLUDE:
            continue
        with open(os.path.join(DOCS_DIR, name), encoding="utf-8") as f:
            for chunk in split_text(f.read()):
                texts.append(chunk)
                sources.append(f"{DOCS_DIR}/{name}")  # 조각의 출처
    return texts, sources


def embed(inputs):
    """문자열 목록을 임베딩해 (개수, DIM) 배열로 반환한다."""
    vectors = []
    for i in range(0, len(inputs), BATCH):
        # 문자열을 하나씩 Content로 감싸야 조각마다 따로 임베딩됨 (그냥 리스트면 하나로 합쳐짐)
        contents = [types.Content(parts=[types.Part.from_text(text=t)]) for t in inputs[i:i + BATCH]]
        result = client.models.embed_content(
            model=EMBED_MODEL, contents=contents,
            config=types.EmbedContentConfig(output_dimensionality=DIM),
        )
        vectors += [e.values for e in result.embeddings]
        if i + BATCH < len(inputs):
            time.sleep(60 * BATCH / PER_MINUTE)  # 분당 한도를 넘지 않게 다음 묶음 전에 쉼
    arr = np.array(vectors, dtype=np.float32)
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)  # 코사인 유사도를 내적으로 계산하려고 정규화


def build_index():
    """모든 조각을 임베딩해 rag_index.npz에 저장한다."""
    texts, sources = load_chunks()
    # 문서용 접두어 (gemini-embedding-2는 task_type 대신 접두어로 용도를 알려줌)
    vectors = embed([f"title: {s} | text: {t}" for t, s in zip(texts, sources)])
    np.savez(INDEX_PATH, vectors=vectors, texts=np.array(texts), sources=np.array(sources))
    print(f"색인 생성: 조각 {len(texts)}개 → {INDEX_PATH}")


def load_index():
    """저장된 색인을 읽는다. 없으면 먼저 만든다."""
    if not os.path.exists(INDEX_PATH):
        build_index()
    data = np.load(INDEX_PATH)
    return data["vectors"], data["texts"], data["sources"]


def search(question, k=TOP_K):
    """질문과 코사인 유사도가 높은 조각 k개를 (점수, 출처, 내용) 목록으로 반환한다."""
    vectors, texts, sources = load_index()
    q = embed([f"task: search result | query: {question}"])[0]  # 질문용 접두어
    scores = vectors @ q  # 정규화된 벡터의 내적 = 코사인 유사도
    top = np.argsort(scores)[::-1][:k]
    return [(float(scores[i]), str(sources[i]), str(texts[i])) for i in top]


def generate(question, hits):
    """검색된 조각을 근거로 답변 텍스트를 생성한다."""
    context = "\n\n".join(f"[{n}] 출처: {s}\n{t}" for n, (_, s, t) in enumerate(hits, 1))
    response = client.models.generate_content(
        model=GEN_MODEL,
        contents=f"[문서 조각]\n{context}\n\n[질문]\n{question}",
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    return response.text


def answer(question):
    """검색한 조각을 근거로 답변을 생성하고, (답변, 검색 결과)를 반환한다."""
    hits = search(question)
    return generate(question, hits), hits


def event(stage, status, log):
    """화면에 보낼 단계 상태 이벤트(working/idle)와 로그를 만든다."""
    return {"agent": stage, "status": status, "log": log}


def rag_events(question):
    """검색 → 답변 생성 단계를 이벤트로 내보내고, 마지막에 답변을 내보낸다 (웹 채팅용)."""
    yield event("rag_search", "working", "질문 임베딩 및 조각 검색 중")
    hits = search(question)
    yield event("rag_search", "idle", f"조각 {len(hits)}개 검색 완료")
    for n, (score, source, text) in enumerate(hits, 1):  # 검색된 조각을 로그로 표시
        preview = " ".join(text.split())[:80]
        yield event("rag_search", "idle", f"[{n}] {score:.3f} {source}\n{preview}...")
    yield event("rag_answer", "working", "조각을 근거로 답변 생성 중")
    text = generate(question, hits)
    yield event("rag_answer", "idle", "답변 생성 완료")
    yield {"reply": text}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or input("질문: ")
    text, hits = answer(q)
    print("\n[검색된 조각]")
    for score, source, _ in hits:
        print(f"  {score:.3f}  {source}")
    print("\n[답변]\n" + text)
