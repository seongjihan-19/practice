"""레드팀 모니터 도구.

사용법
  python bm/monitor/redteam_tool.py serve [--port 8765]   모니터 페이지 서버 실행
  python bm/monitor/redteam_tool.py start                  새 실행 시작 (3개 모두 '대기')
  python bm/monitor/redteam_tool.py agent <이름> running    에이전트 실행 중으로 표시
  python bm/monitor/redteam_tool.py agent <이름> done       에이전트 완료로 표시
  python bm/monitor/redteam_tool.py import                 bm/redteam/*.md 원문에서 지적을 읽어 표로 합침
  python bm/monitor/redteam_tool.py applied <번호...>       캔버스 반영 완료로 표시

에이전트 이름: redteam-investor, redteam-customer, redteam-competitor
레드팀 실행 자체는 Claude Code 세션이 서브에이전트로 한다. 이 도구는 상태 · 로그 · 결정만 다룬다.
"""
import json
import re
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
BM = HERE.parent
RT = BM / "redteam"
STATUS = RT / "status.json"
ITEMS = RT / "items.json"
EVENTS = RT / "run_log.jsonl"
LOG_MD = BM / "redteam_log.md"
PAGE = HERE / "monitor.html"

AGENTS = {
    "redteam-investor": "투자자",
    "redteam-customer": "고객",
    "redteam-competitor": "경쟁사",
}
# 버튼 → CLAUDE.md 결정값
DECISION_MAP = {"수용": "반영", "수정": "반영", "반려": "반박"}

LOCK = threading.Lock()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def default_status():
    return {
        "run_id": None,
        "state": "idle",
        "requested_at": None,
        "agents": {a: {"state": "idle", "started": None, "finished": None} for a in AGENTS},
    }


def log_event(msg, agent=None):
    RT.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": now(), "agent": agent, "msg": msg}, ensure_ascii=False) + "\n")


def read_events(limit=200):
    if not EVENTS.exists():
        return []
    lines = EVENTS.read_text(encoding="utf-8").splitlines()[-limit:]
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            pass
    return out


def refresh_overall(st):
    states = [v["state"] for v in st["agents"].values()]
    if any(s == "running" for s in states):
        st["state"] = "running"
    elif all(s == "done" for s in states):
        st["state"] = "done"
    return st


# ---------- 원문 파싱 ----------
ROW_ID = re.compile(r"^[ICK]-\d+$")


def parse_raw(agent):
    path = RT / f"{agent}.md"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or not ROW_ID.match(cells[0]):
            continue
        cells += [""] * (6 - len(cells))
        rows.append({
            "id": cells[0],
            "agent": agent,
            "cell": cells[1],
            "issue": cells[2],
            "evidence": cells[3],
            "severity": cells[4],
        })
    return rows


def import_items():
    old = {i["id"]: i for i in read_json(ITEMS, [])}
    items = []
    for agent in AGENTS:
        for r in parse_raw(agent):
            prev = old.get(r["id"], {})
            r.update({
                "button": prev.get("button", ""),
                "decision": prev.get("decision", ""),
                "edit": prev.get("edit", ""),
                "decided_at": prev.get("decided_at"),
                "applied": prev.get("applied", False),
            })
            items.append(r)
    write_json(ITEMS, items)
    write_log_md(items)
    return items


def md(s):
    return str(s or "").replace("|", "\\|").replace("\n", " ")


def write_log_md(items):
    blank = sum(1 for i in items if not i["decision"])
    lines = [
        "# 레드팀 로그 — bm_canvas.md 검증",
        "",
        f"- 갱신: {now()}",
        f"- 지적 {len(items)}건 · 결정 빈칸 {blank}개",
        "- 결정값: 수용 → `반영` / 수정 → `반영`(수정 내용대로) / 반려 → `반박`",
        "- CLAUDE.md 규칙: 결정이 `반영`인 줄만 캔버스를 고친다. `보류` · `반박` 줄은 고치지 않는다.",
        "- 원문: bm/redteam/redteam-investor.md · redteam-customer.md · redteam-competitor.md",
        "",
        "| 번호 | 레드팀 | 대상 칸 | 지적 내용 | 근거 | 심각도 | 버튼 | 결정 | 수정 내용 | 캔버스 반영 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i in items:
        applied = "완료" if i["applied"] else ("대기" if i["decision"] == "반영" else "—")
        lines.append(
            f"| {md(i['id'])} | {AGENTS.get(i['agent'], i['agent'])} | {md(i['cell'])} | {md(i['issue'])} | "
            f"{md(i['evidence'])} | {md(i['severity'])} | {md(i['button'])} | {md(i['decision'])} | "
            f"{md(i['edit'])} | {applied} |"
        )
    LOG_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def decide(item_id, button, edit=""):
    if button not in DECISION_MAP:
        raise ValueError("button must be 수용/수정/반려")
    if button == "수정" and not edit.strip():
        raise ValueError("수정 내용을 입력해야 합니다")
    items = read_json(ITEMS, [])
    for i in items:
        if i["id"] == item_id:
            if i.get("applied"):
                raise ValueError("이미 캔버스에 반영된 항목은 바꿀 수 없습니다")
            i["button"] = button
            i["decision"] = DECISION_MAP[button]
            i["edit"] = edit.strip() if button == "수정" else ""
            i["decided_at"] = now()
            write_json(ITEMS, items)
            write_log_md(items)
            log_event(f"{item_id} {button} → 결정 '{i['decision']}'" + (f" · 수정: {i['edit']}" if i["edit"] else ""), i["agent"])
            return i
    raise KeyError(item_id)


def state_payload():
    return {
        "status": read_json(STATUS, default_status()),
        "events": read_events(),
        "items": read_json(ITEMS, []),
        "agents": AGENTS,
    }


# ---------- 서버 ----------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html", "/monitor.html"):
            return self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/state":
            with LOCK:
                return self.send(200, state_payload())
        self.send(404, {"error": "not found"})

    def do_POST(self):
        try:
            with LOCK:
                if self.path == "/api/run":
                    st = read_json(STATUS, default_status())
                    if st["state"] in ("requested", "running"):
                        return self.send(409, {"error": "이미 실행 요청 중입니다"})
                    st = default_status()
                    st["state"] = "requested"
                    st["requested_at"] = now()
                    write_json(STATUS, st)
                    log_event("실행 버튼 — 레드팀 3개 실행 요청. Claude Code 세션에서 실행을 시작해야 합니다.")
                    return self.send(200, state_payload())
                if self.path == "/api/decide":
                    b = self.body()
                    decide(b.get("id", ""), b.get("button", ""), b.get("edit", ""))
                    return self.send(200, state_payload())
            self.send(404, {"error": "not found"})
        except (ValueError, KeyError) as e:
            self.send(400, {"error": str(e)})


def serve(port):
    RT.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"레드팀 모니터: http://127.0.0.1:{port}", flush=True)
    srv.serve_forever()


# ---------- 세션용 명령 ----------
def main(argv):
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    if cmd == "serve":
        port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
        return serve(port)
    with LOCK:
        if cmd == "start":
            st = default_status()
            st["run_id"] = datetime.now().strftime("%Y%m%d-%H%M%S")
            st["state"] = "running"
            st["requested_at"] = now()
            write_json(STATUS, st)
            log_event(f"실행 시작 (run {st['run_id']}) — 레드팀 3개 동시 실행")
            return 0
        if cmd == "agent":
            name, state = argv[1], argv[2]
            st = read_json(STATUS, default_status())
            a = st["agents"][name]
            a["state"] = state
            if state == "running":
                a["started"] = now()
                log_event("검토 시작", name)
            elif state == "done":
                a["finished"] = now()
                log_event(f"검토 완료 — 원문 저장: bm/redteam/{name}.md", name)
            write_json(STATUS, refresh_overall(st))
            if st["state"] == "done":
                log_event("레드팀 3개 모두 완료")
            return 0
        if cmd == "import":
            items = import_items()
            log_event(f"원문 {len(AGENTS)}개를 bm/redteam_log.md 표로 합침 — 지적 {len(items)}건")
            print(f"{len(items)} items")
            return 0
        if cmd == "applied":
            ids = set(argv[1:])
            items = read_json(ITEMS, [])
            for i in items:
                if i["id"] in ids and i["decision"] == "반영":
                    i["applied"] = True
                    log_event(f"{i['id']} 캔버스 반영 완료", i["agent"])
            write_json(ITEMS, items)
            write_log_md(items)
            return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
