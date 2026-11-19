import glob
import os

import yaml
from google.genai import types

from agent_loop import run_agent
from config import make_client
from tool import QUERY_TABLE, SEARCH_DOCS, query_table, search_docs

# 도구 이름 → (도구 명세, 실제 함수)
TOOL_REGISTRY = {"search_docs": (SEARCH_DOCS, search_docs), "query_table": (QUERY_TABLE, query_table)}


def load_yaml(path):
    """YAML 파일 하나를 dict로 읽는다."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


TEMPLATE = load_yaml("agents/_template.yaml")  # 공용 템플릿 + 보고 양식
# agents/ 의 에이전트 정의 파일들 ('_'로 시작하는 템플릿 파일은 제외)
AGENTS = {a["name"]: a for a in (load_yaml(p) for p in sorted(glob.glob("agents/*.yaml"))
                                 if not os.path.basename(p).startswith("_"))}


def system_prompt(agent):
    """공용 템플릿 + 에이전트 역할 + 보고 양식을 합쳐 시스템 프롬프트를 만든다."""
    return "\n".join([TEMPLATE["common"], agent["role"], TEMPLATE["report"]])


def web_sources(response):
    """Google 검색 응답의 grounding_metadata에서 웹 출처 목록을 뽑는다."""
    meta = response.candidates[0].grounding_metadata
    chunks = (meta.grounding_chunks or []) if meta else []
    return [f"- {c.web.title}: {c.web.uri}" for c in chunks if c.web]


def run_web(client, model, prompt, task):
    """Google 검색 도구로 답하고, 실제 검색 출처를 답 끝에 덧붙인다. 실패하면 보고 양식으로 알린다."""
    config = types.GenerateContentConfig(
        system_instruction=prompt,
        tools=[types.Tool(google_search=types.GoogleSearch())],  # Gemini 내장 Google 검색
    )
    try:
        response = client.models.generate_content(model=model, contents=task, config=config)
    except Exception as e:  # 검색 실패를 다른 내용으로 메우지 않고 그대로 보고
        return f"[결과]\n웹 검색을 하지 못했습니다.\n[근거]\n없음\n[확인하지 못한 점]\n웹 검색 도구 오류: {e}"
    sources = web_sources(response)
    return response.text + ("\n\n[검색 출처]\n" + "\n".join(sources) if sources else "")


def run_yaml_agent(name, task):
    """YAML로 정의된 서브 에이전트가 자기 API 키와 도구로 task를 수행하고 보고문을 반환한다."""
    agent = AGENTS[name]
    client, model = make_client(agent["env"])  # 에이전트 전용 클라이언트
    prompt = system_prompt(agent)
    if "google_search" in agent["tools"]:
        return run_web(client, model, prompt, task)
    tools = [types.Tool(function_declarations=[TOOL_REGISTRY[t][0] for t in agent["tools"]])]
    functions = {t: TOOL_REGISTRY[t][1] for t in agent["tools"]}
    return run_agent(client, model, prompt, tools, functions, task)  # 기존 도구 호출 루프 그대로 사용
