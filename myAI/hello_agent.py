"""hello_agent.py - Claude Code 구독으로 동작하는 터미널 대화 에이전트.

Claude Agent SDK(claude-agent-sdk)는 이 PC에 로그인된 Claude Code를 통해
Claude를 호출하므로, API 키 없이 Claude Code 구독제로 사용됩니다.
'quit' 를 입력하면 종료합니다.
"""

import asyncio

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    query,
)

MODEL = "claude-sonnet-5-5"
SYSTEM_PROMPT = "안녕 나는 너의 다정한 친구 클로드야"

# 대화 기록: {"role": "user" | "assistant", "content": "..."} 를 차례로 쌓습니다.
history: list[dict[str, str]] = []

options = ClaudeAgentOptions(
    model=MODEL,
    system_prompt=SYSTEM_PROMPT,
    tools=["WebSearch", "WebFetch"],              # 파일/쉘 같은 도구 없이 순수 대화만
    allowed_tools=["WebSearch", "WebFetch"],
    max_turns=5,           # 한 번 묻고 한 번 답하기
    setting_sources=[],    # 폴더의 CLAUDE.md 등 설정을 불러오지 않음
)


def build_prompt() -> str:
    """history 리스트 전체를 하나의 프롬프트로 만들어 이전 대화를 기억하게 합니다."""
    lines = ["지금까지의 대화 기록입니다. 마지막 사용자 메시지에 대답해 주세요.\n"]
    for msg in history:
        speaker = "사용자" if msg["role"] == "user" else "클로드"
        lines.append(f"{speaker}: {msg['content']}")
    return "\n".join(lines)


async def ask_claude() -> str:
    reply_parts: list[str] = []
    async for message in query(prompt=build_prompt(), options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    reply_parts.append(block.text)
    return "".join(reply_parts).strip()


async def main() -> None:
    print(f"클로드: {SYSTEM_PROMPT}")
    print("(종료하려면 'quit' 입력)\n")

    while True:
        try:
            user_input = input("나: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        history.append({"role": "user", "content": user_input})
        try:
            reply = await ask_claude()
        except Exception as e:  # CLI 미설치, 로그인 안 됨 등
            history.pop()
            print(f"[오류] {e}\n")
            continue

        history.append({"role": "assistant", "content": reply})
        print(f"클로드: {reply}\n")

    print("클로드: 다음에 또 이야기하자! 안녕 👋")


if __name__ == "__main__":
    asyncio.run(main())
