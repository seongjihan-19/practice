from google.genai import types

from config import make_client

# 서브 에이전트별 .env 접두어와 역할(시스템 프롬프트)
SUB_AGENTS = {
    "research_agent": ("RESEARCH", "너는 리서치 전문가다. 주어진 주제에 대해 핵심 사실과 배경을 조사해 자세히 정리한다."),
    "writer_agent": ("WRITER", "너는 작성 전문가다. 주어진 자료와 요구사항을 바탕으로 목적에 맞는 글을 완성도 있게 작성한다."),
    "reviewer_agent": ("REVIEWER", "너는 검토 전문가다. 주어진 글의 사실 오류·논리·문장을 점검하고 구체적인 개선점과 수정본을 제시한다."),
}


def run_sub_agent(name, task):
    """name에 해당하는 서브 에이전트가 자기 API 키로 task를 수행하고 결과 텍스트를 반환한다."""
    prefix, system_prompt = SUB_AGENTS[name]
    client, model = make_client(prefix)  # 서브 에이전트 전용 클라이언트
    response = client.models.generate_content(
        model=model,
        contents=task,
        config=types.GenerateContentConfig(system_instruction=system_prompt),  # 역할 지정
    )
    return response.text
