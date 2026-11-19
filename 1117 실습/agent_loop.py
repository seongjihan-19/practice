from google.genai import types


def call_tool(fc, functions):
    """모델이 요청한 도구 함수를 실행하고 결과(또는 오류)를 dict로 반환한다."""
    try:
        return {"result": functions[fc.name](**fc.args)}  # 이름으로 실제 함수를 찾아 실행
    except Exception as e:
        return {"error": str(e)}  # 오류도 모델에게 알려줌


def run_agent(client, model, system_prompt, tools, functions, user_message, max_turns=10, on_event=None):
    """도구 호출이 없어질 때까지 모델 호출과 도구 실행을 반복하고 최종 답변을 반환한다.

    tools: types.Tool 목록 (도구 명세), functions: {도구 이름: 실제 함수}
    on_event: 도구를 실행할 때마다 (이름, 인자, 결과)로 불리는 함수 (선택)
    """
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),  # 루프를 직접 돌림
    )
    history = [types.Content(role="user", parts=[types.Part.from_text(text=user_message)])]
    for _ in range(max_turns):  # 무한 반복 방지
        response = client.models.generate_content(model=model, contents=history, config=config)
        if not response.function_calls:  # 도구 호출이 없으면 최종 답변
            return response.text
        history.append(response.candidates[0].content)  # 모델 턴을 그대로 보존 (thought signature 포함)
        parts = []
        for fc in response.function_calls:
            result = call_tool(fc, functions)
            if on_event:
                on_event(fc.name, dict(fc.args), result)
            parts.append(types.Part.from_function_response(name=fc.name, response=result))
        history.append(types.Content(role="user", parts=parts))  # API는 user/model 역할만 허용
    return "최대 반복 횟수에 도달해 답변을 완성하지 못했습니다."
