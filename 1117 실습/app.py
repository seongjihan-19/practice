from collections.abc import Iterable

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from orchestrator import orchestrate
from rag import rag_events
from agentic_rag import agentic_events
from multi_rag import multi_rag_events

app = FastAPI()


class ChatRequest(BaseModel):
    message: str  # 채팅창에서 보낸 사용자 메시지


@app.get("/")
def index():
    """채팅 UI 페이지를 돌려준다."""
    return FileResponse("static/index.html")


@app.post("/chat")
def chat(req: ChatRequest) -> Iterable[dict]:
    """에이전트 상태 이벤트와 최종 답변을 JSON Lines로 한 줄씩 스트리밍한다."""
    yield from orchestrate(req.message)  # 동기 제너레이터라 스레드풀에서 실행되어 서버를 막지 않음


@app.post("/rag")
def rag_chat(req: ChatRequest) -> Iterable[dict]:
    """RAG(검색 → 답변) 단계 이벤트와 답변을 JSON Lines로 스트리밍한다. 에이전트는 쓰지 않는다."""
    yield from rag_events(req.message)


@app.post("/agentic-rag")
def agentic_rag_chat(req: ChatRequest) -> Iterable[dict]:
    """Agentic RAG(에이전트가 검색 여부·검색어를 스스로 정함) 이벤트와 답변을 스트리밍한다."""
    yield from agentic_events(req.message)


@app.post("/multi-rag")
def multi_rag_chat(req: ChatRequest) -> Iterable[dict]:
    """Multi-Agentic RAG(오케스트레이터가 문서·웹·표 검색 에이전트에 위임) 이벤트와 답변을 스트리밍한다."""
    yield from multi_rag_events(req.message)
