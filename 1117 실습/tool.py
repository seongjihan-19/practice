import csv

from google.genai import types

from rag import search

# search_docs 도구 명세 (모델이 보고 언제·어떻게 호출할지 판단함)
SEARCH_DOCS = types.FunctionDeclaration(
    name="search_docs",
    description="화장품 제품 개발 문서(브랜드·라인 규칙·원료·가격·원가·OEM·광고 표현·기후·대구 자산)에서 검색어와 관련된 문서 조각을 찾는다.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "사용자 문장이 아닌 핵심 키워드로 다시 쓴 검색어"},
        },
        "required": ["query"],
    },
)


def search_docs(query):
    """검색어로 문서 조각을 찾아 '조각 본문 + 출처 파일명' 문자열로 반환한다."""
    hits = search(query)  # rag.py의 numpy 코사인 유사도 검색 재사용
    return "\n\n".join(f"[{n}] 출처: {source}\n{text}" for n, (_, source, text) in enumerate(hits, 1))


TOOLS = [types.Tool(function_declarations=[SEARCH_DOCS])]  # 모델에 넘길 도구 목록
FUNCTIONS = {"search_docs": search_docs}  # 도구 이름 → 실제 함수

TABLE_PATH = "docs/OEM_업체비교표.csv"
TABLE_COLUMNS = "업체, 위치, OEM·위탁생산, ODM(처방 개발), CGMP 인증, 기능성 화장품, 한방·식물 원료, 연구·시험 설비, 근거 등급, 우선순위"

# query_table 도구 명세 (OEM 후보 업체 비교표 CSV 조회)
QUERY_TABLE = types.FunctionDeclaration(
    name="query_table",
    description=f"OEM 후보 업체 비교표(CSV)에서 행을 조회한다. 열: {TABLE_COLUMNS}. "
    "표시: ✅ 공개 자료로 확인, ❓ 미확인, ❌ 해당 없음. 인자를 비우면 전체 표를 돌려준다.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "column": {"type": "string", "description": "조건을 걸 열 이름 (비우면 모든 열에서 찾음)"},
            "keyword": {"type": "string", "description": "그 열 값에 포함되어야 하는 글자 (예: '✅', '대구 달서구', '1')"},
        },
    },
)


def query_table(column="", keyword=""):
    """CSV에서 조건에 맞는 행을 '출처 + 열=값' 문자열로 반환한다."""
    with open(TABLE_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if column and column not in rows[0]:
        return f"'{column}' 열이 없습니다. 열 목록: {TABLE_COLUMNS}"
    hits = [r for r in rows if keyword in (r[column] if column else " ".join(r.values()))]  # 조건 맞는 행만
    lines = [" | ".join(f"{k}={v}" for k, v in r.items()) for r in hits]
    return f"출처: {TABLE_PATH} (전체 {len(rows)}행 중 {len(hits)}행)\n" + "\n".join(lines)
