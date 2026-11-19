from google.genai import types

from config import make_client
from sub_agents import run_sub_agent

SYSTEM_PROMPT = (
    "너는 오케스트레이터다. 사용자 요청을 분석해 필요한 서브 에이전트(도구)를 골라 작업을 맡기고, "
    "받은 결과를 종합해 사용자에게 최종 답변한다. 필요하면 여러 에이전트를 순서대로 호출한다.\n"
    # 서브 에이전트는 대화 기록을 못 보므로 자료 전문을 task에 넣도록 지시
    "중요: 서브 에이전트는 이 대화와 다른 에이전트의 결과를 전혀 볼 수 없고, task 문자열만 받는다. "
    "따라서 '방금 조사한', '작성된 보고서' 같은 지칭만 쓰지 말고, 이전 에이전트가 만든 결과물 전문을 "
    "task 안에 그대로 붙여 넣어 전달한다."
)

# 서브 에이전트 이름과 설명 (오케스트레이터가 보고 위임 대상을 판단함)
AGENT_DESCRIPTIONS = {
    "research_agent": "주제에 대한 사실·배경 조사가 필요할 때 호출한다.",
    "writer_agent": "조사 자료나 요구사항을 바탕으로 글(보고서·요약·답변 등)을 작성해야 할 때 호출한다. task에 필요한 자료를 포함한다.",
    "reviewer_agent": "작성된 글의 오류·논리·문장을 검토하고 개선해야 할 때 호출한다. task에 검토할 글 전체를 포함한다.",
}


def make_declaration(name, description):
    """서브 에이전트 하나를 오케스트레이터용 함수 선언으로 만든다."""
    return types.FunctionDeclaration(
        name=name,
        description=description,
        parameters_json_schema={  # 서브 에이전트에게 넘길 작업 지시문 하나만 받음
            "type": "object",
            "properties": {"task": {"type": "string", "description": "서브 에이전트에게 맡길 구체적인 작업 내용. 서브 에이전트는 대화를 볼 수 없으므로 필요한 자료(이전 결과물) 전문을 반드시 포함한다."}},
            "required": ["task"],
        },
    )


def make_config():
    """서브 에이전트 도구와 시스템 프롬프트를 담은 설정을 만든다."""
    declarations = [make_declaration(n, d) for n, d in AGENT_DESCRIPTIONS.items()]
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=declarations)],  # 서브 에이전트들을 도구로 등록
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),  # 자동 호출 끔
    )


def ask_orchestrator(contents):
    """오케스트레이터 모델을 한 번 호출하고 응답을 반환한다."""
    client, model = make_client("ORCHESTRATOR")  # 오케스트레이터 전용 클라이언트
    return client.models.generate_content(model=model, contents=contents, config=make_config())


def event(agent, status, log):
    """화면에 보낼 에이전트 상태 이벤트(working/idle)와 로그를 만든다."""
    return {"agent": agent, "status": status, "log": log}


def call_agent(fc):
    """서브 에이전트 하나를 실행하며 상태 이벤트를 내보내고, 마지막에 function_response 파트를 반환한다."""
    task = fc.args["task"]
    yield event(fc.name, "working", f"작업 시작: {task}")  # 작업 시작 알림 (blink 시작)
    try:
        text = run_sub_agent(fc.name, task)  # 서브 에이전트에게 위임
        result, log = {"result": text}, f"작업 완료: {text[:80]}..."
    except Exception as e:
        result, log = {"error": str(e)}, f"오류: {e}"  # 오류도 모델에게 알려줌
    yield event(fc.name, "idle", log)  # 작업 종료 알림 (blink 끝)
    return types.Part.from_function_response(name=fc.name, response=result)


def orchestrate(user_message):
    """서브 에이전트 호출을 반복하며 상태 이벤트를 내보내고, 마지막에 최종 답변을 내보낸다."""
    history = [types.Content(role="user", parts=[types.Part.from_text(text=user_message)])]
    while True:
        yield event("orchestrator", "working", "요청 분석 및 판단 중")
        response = ask_orchestrator(history)
        if not response.function_calls:  # 더 위임할 일이 없으면 최종 답변
            yield event("orchestrator", "idle", "최종 답변 종합 완료")
            yield {"reply": response.text}
            return
        names = ", ".join(fc.name for fc in response.function_calls)
        yield event("orchestrator", "idle", f"위임 결정: {names}")
        history.append(response.candidates[0].content)  # 모델 턴을 그대로 보존 (thought signature 포함)
        parts = []
        for fc in response.function_calls:
            parts.append((yield from call_agent(fc)))  # 서브 에이전트 이벤트를 그대로 흘려보내고 결과 파트를 받음
        history.append(types.Content(role="user", parts=parts))  # API는 user/model 역할만 허용
