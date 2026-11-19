import queue
import re
import sys
import threading

from agent_loop import run_agent
from config import make_client
from tool import FUNCTIONS, TOOLS

SYSTEM_PROMPT = """너는 화장품 제품 개발 문서를 근거로 답하는 에이전트야. search_docs 도구로 문서를 찾을 수 있어.

* 일반 상식에 해당하는 문서가 필요없는 질문은 검색하지 않고 대답하고,
* 검색어는 사용자의 문장을 그대로 쓰지 말고, 핵심 키워드로 다시 쓴다.
* 질문에 주제가 여럿이면 주제마다 따로 검색한다.
* 결과에 답이 없으면 다른 검색어로 다시 찾는다. 같은 검색어을 반복하지 않는다.
* 검색은 최대 5번으로 제한한다.

검색된 문서에 있는 내용만 근거로 답하고,
문장마다 출처 파일명을 괄호로 적고, 끝내 찾지 못한 내용은 추측하지 말고, 문서에서 찾지 못했습니다 라고 답변해야 한다."""

client, MODEL = make_client("RAG")  # .env의 RAG_API_KEY, RAG_MODEL 사용


def sources_of(text):
    """search_docs 결과 문자열에서 조각 출처 목록을 뽑는다."""
    # 조각 본문에도 '출처:'가 나올 수 있어서, 조각 머리줄 "[n] 출처: ..."만 골라냄
    return [m.group(1) for m in re.finditer(r"^\[\d+\] 출처: (.+)$", text, re.M)]


def show_call(name, args, result):
    """도구 호출 내역(검색어와 찾은 출처)을 화면에 출력한다."""
    print(f"[도구 호출] {name}({args}) → {sources_of(result.get('result', '')) or result.get('error')}")


def event(node, status, log):
    """화면에 보낼 상태 이벤트(working/idle)와 로그를 만든다."""
    return {"agent": node, "status": status, "log": log}


def agentic_events(question):
    """에이전트 진행 상황(검색어·찾은 출처)을 이벤트로 내보내고, 마지막에 답변을 내보낸다 (웹 채팅용)."""
    events, count = queue.Queue(), [0]

    def traced_search(query):
        """search_docs를 실행하면서 검색 시작·끝을 이벤트로 알린다."""
        count[0] += 1
        events.put(event("ag_search", "working", f"검색 {count[0]}: '{query}'"))
        text = FUNCTIONS["search_docs"](query)
        found = list(dict.fromkeys(sources_of(text)))  # 중복 뺀 출처
        events.put(event("ag_search", "idle", f"검색 {count[0]} 결과: {', '.join(found)}"))
        return text

    def work():
        """run_agent를 돌리고 최종 답변(또는 오류)을 큐에 넣는다."""
        try:
            reply = run_agent(client, MODEL, SYSTEM_PROMPT, TOOLS, {"search_docs": traced_search}, question)
        except Exception as e:
            reply = f"오류: {e}"
        events.put(event("ag_agent", "idle", f"최종 답변 완료 (검색 {count[0]}번)"))
        events.put({"reply": reply})

    yield event("ag_agent", "working", "질문 분석 · 검색 여부 판단 중")
    threading.Thread(target=work, daemon=True).start()  # run_agent는 끝날 때까지 막히므로 별도 스레드에서 실행
    while True:
        item = events.get()  # 스레드가 넣는 이벤트를 받는 대로 내보냄
        yield item
        if "reply" in item:
            return


def ask(question):
    """질문을 에이전트 루프(run_agent)에 넘겨 최종 답변을 받는다."""
    return run_agent(client, MODEL, SYSTEM_PROMPT, TOOLS, FUNCTIONS, question, on_event=show_call)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or input("질문: ")
    print("\n[답변]\n" + ask(q))
