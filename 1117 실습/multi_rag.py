import sys

import orchestrator
from yaml_agents import AGENTS, run_yaml_agent

# 기존 오케스트레이터 시스템 프롬프트에 덧붙일 Multi-Agentic RAG 규칙
RULES = """
[Multi-Agentic RAG 규칙]
- 기획 내부 결정은 docs 폴더에서(doc_searcher, 업체 비교표 조회는 data_analyst), 외부사실은 웹에서(web_searcher) 검색한다.
- 답의 문장마다 출처를 표기한다.
- 한 출처에서 못 찾은 내용이 있다면 다른 출처로 메꾸지 않는다. 못 찾았다고 그대로 적는다.
- 사용자의 질문을 task에 그대로 넣지 말고, 각 서브 에이전트가 맡을 부분만 구체적인 검색·조회 지시로 다시 써서 넘긴다."""

SYSTEM_PROMPT = orchestrator.SYSTEM_PROMPT + RULES
DESCRIPTIONS = {name: agent["description"] for name, agent in AGENTS.items()}  # YAML의 설명으로 등록


def multi_rag_events(question):
    """오케스트레이터의 에이전트 목록·프롬프트만 바꿔 끼워 orchestrate를 그대로 실행한다."""
    saved = orchestrator.SYSTEM_PROMPT, orchestrator.AGENT_DESCRIPTIONS, orchestrator.run_sub_agent
    # 위임 로직은 그대로 두고 목록·프롬프트·실행 함수만 교체
    orchestrator.SYSTEM_PROMPT, orchestrator.AGENT_DESCRIPTIONS, orchestrator.run_sub_agent = (
        SYSTEM_PROMPT, DESCRIPTIONS, run_yaml_agent)
    try:
        yield from orchestrator.orchestrate(question)
    finally:
        orchestrator.SYSTEM_PROMPT, orchestrator.AGENT_DESCRIPTIONS, orchestrator.run_sub_agent = saved  # 원래대로 복구


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or input("질문: ")
    for item in multi_rag_events(q):
        print(item.get("reply") or f"[{item['agent']}] {item['log']}")
