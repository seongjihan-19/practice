"""Claude Code 훅 이벤트 기록기.

Claude Code가 훅으로 stdin에 넘겨주는 JSON을 받아
초 단위 타임스탬프(ts)를 붙여 JSON Lines 파일에 한 줄씩 추가한다.

- 프로젝트 루트: 환경변수 VOC_PROJECT_ROOT
  (없으면 CLAUDE_PROJECT_DIR, 그것도 없으면 이 파일 기준 두 단계 위 폴더)
- 기록 위치: <프로젝트 루트>/ax/demo/logs/events.jsonl (폴더가 없으면 만든다)
- tool_response: 항상 기록하며, 문자열로 바꾼 뒤 앞 600자만 남긴다.
- 기록에 실패해도 Claude Code 작업을 막지 않도록 항상 종료 코드 0으로 끝낸다.
"""

import json
import os
import sys
import time
from pathlib import Path

ROOT_ENV = "VOC_PROJECT_ROOT"
LOG_RELATIVE = Path("ax") / "demo" / "logs" / "events.jsonl"
RESPONSE_LIMIT = 600


def project_root() -> Path:
    for name in (ROOT_ENV, "CLAUDE_PROJECT_DIR"):
        value = os.environ.get(name)
        if value:
            return Path(value)
    # .claude/hooks/log_event.py -> 프로젝트 루트
    return Path(__file__).resolve().parents[2]


def read_payload() -> dict:
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"parse_error": True, "raw": raw[:RESPONSE_LIMIT]}
    return data if isinstance(data, dict) else {"payload": data}


def truncate_response(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    return value[:RESPONSE_LIMIT]


def main() -> None:
    payload = read_payload()

    record = {"ts": int(time.time())}
    record.update(payload)
    record["tool_response"] = truncate_response(payload.get("tool_response"))

    log_path = project_root() / LOG_RELATIVE
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # 기록 실패가 Claude Code 작업을 막지 않게 한다
        print(f"log_event: {exc}", file=sys.stderr)
    sys.exit(0)
