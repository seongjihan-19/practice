"""에이전트 대시보드 로컬 서버.

실행:  python dashboard_server.py   →  http://127.0.0.1:8765

- POST /api/run   : pipeline.json 순서대로 에이전트(claude -p --agent <이름>) 실행
- POST /api/stop  : 실행 중인 에이전트 프로세스를 모두 종료하고 '중단' 로그를 남김
- GET  /api/state : 에이전트 상태·진행 출력, run_log.jsonl, 시나리오별 월 손익, 검토 지적사항

run_log.jsonl 기록 규칙은 CLAUDE.md를 따릅니다. 에이전트는 마지막 줄에 RUN_LOG: {json}을 출력하고,
서버가 run_id·시각·입력 파일 해시 등을 채워 한 줄씩 추가(append)합니다.
"""
import collections
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.join(BASE, "pipeline.json")
LOG = os.environ.get("DASHBOARD_LOG") or os.path.join(BASE, "run_log.jsonl")  # 시험용으로 다른 로그 파일 지정 가능
HTML = os.path.join(BASE, "dashboard.html")
HOST, PORT = "127.0.0.1", int(os.environ.get("DASHBOARD_PORT", "8765"))
CLAUDE_CMD = os.environ.get("CLAUDE_BIN")  # 시험용 대체 실행 파일 경로(.py면 python으로 실행)
KST = dt.timezone(dt.timedelta(hours=9))

RUN_LOG_INSTRUCTION = """

---
[대시보드 실행 규칙]
- 이 작업은 대시보드에서 비대화형으로 실행된다. 사용자에게 질문하지 말고 할 수 있는 범위까지 진행하라.
- Python은 `python -I -X utf8 ...` 형태로, 작업 폴더에서 바로 실행하라(앞에 cd를 붙이지 마라).
- 응답의 맨 마지막 줄은 반드시 아래 형식 한 줄이어야 한다. 줄바꿈 없는 JSON 객체 하나다.
RUN_LOG: {"status":"완료|일부|중단","changes":[],"sources":[],"assumptions_used":[],"outputs":[],"checklist":[],"decision":null,"open_issues":[],"verification":{"method":"","not_verified":[]},"next_step":"","findings":[]}
- 각 필드의 형식은 CLAUDE.md '실행 로그 규칙'의 필드 표를 따른다. run_id·timestamp·inputs 등은 서버가 채운다.
- findings 항목 형식: {"severity":"치명|주의|개선","stage":"playbook 단계·항목","location":"엑셀 셀 또는 문서 위치","problem":"","suggestion":""}
- 숫자는 엑셀 셀에서 읽은 값만 쓰고 셀 위치를 남겨라. 확인하지 못한 내용은 "[확인필요]"로 적어라.
"""

lock = threading.RLock()
log_lock = threading.Lock()
state = {"running": False, "stop_requested": False, "started_at": None, "ended_at": None, "message": "대기 중"}
agents = collections.OrderedDict()
procs = {}  # agent -> Popen


def now_iso():
    return dt.datetime.now(KST).isoformat(timespec="seconds")


def load_pipeline():
    with open(PIPELINE, encoding="utf-8") as f:
        return json.load(f)


def reset_agents(pipe):
    with lock:
        agents.clear()
        for group in pipe["groups"]:
            for step in group:
                agents[step["agent"]] = {
                    "agent": step["agent"], "stage": step["stage"], "stage_name": step["stage_name"],
                    "status": "idle", "started_at": None, "ended_at": None, "cost_usd": None,
                    "events": collections.deque(maxlen=80),
                }


def push_event(name, kind, text):
    with lock:
        a = agents.get(name)
        if a is not None:
            a["events"].append({"t": dt.datetime.now(KST).strftime("%H:%M:%S"), "kind": kind, "text": text[:400]})


# ---------- run_log.jsonl ----------
def read_log():
    rows = []
    if not os.path.exists(LOG):
        return rows
    with open(LOG, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"_invalid": True, "_line": i, "raw": line[:300]})
    return rows


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def append_log(pipe, step, agent_part, request):
    with log_lock:
        rows = [r for r in read_log() if not r.get("_invalid")]
        nums = [int(r["run_id"][1:]) for r in rows if str(r.get("run_id", "")).startswith("R") and r["run_id"][1:].isdigit()]
        run_id = f"R{(max(nums) + 1) if nums else 1:04d}"
        model = os.path.join(BASE, pipe["model_file"])
        files = []
        if os.path.exists(model):
            files.append({"path": pipe["model_file"],
                          "modified": dt.datetime.fromtimestamp(os.path.getmtime(model), KST).isoformat(timespec="seconds"),
                          "sha256": sha256(model)})
        rec = {
            "run_id": run_id, "timestamp": now_iso(), "project": pipe["project"], "model_file": pipe["model_file"],
            "stage": step["stage"], "stage_name": step["stage_name"], "agent": step["agent"],
            "status": "일부", "request": request, "parent_run_id": rows[-1]["run_id"] if rows else None, "corrects": None,
            "inputs": {"files": files, "depends_on_stages": []},
            "changes": [], "sources": [], "assumptions_used": [], "outputs": [], "checklist": [],
            "decision": None, "open_issues": [], "verification": {"method": "", "not_verified": []},
            "backup": None, "next_step": "",
        }
        for k, v in (agent_part or {}).items():
            if k not in ("run_id", "timestamp", "project", "model_file", "stage", "stage_name", "agent",
                         "request", "parent_run_id", "inputs", "backup"):
                rec[k] = v
        line = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
        json.loads(line)  # 형식 검증
        with open(LOG, "a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")
        return run_id


def extract_run_log(text):
    if not text:
        return None
    idx = text.rfind("RUN_LOG:")
    if idx < 0:
        return None
    brace = text.find("{", idx)
    if brace < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[brace:])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


# ---------- 에이전트 실행 ----------
def summarize_tool(name, inp):
    inp = inp or {}
    for key in ("command", "file_path", "pattern", "query", "url", "path", "description"):
        if inp.get(key):
            return f"{name}: {str(inp[key])[:160]}"
    return name


def run_step(pipe, step):
    name = step["agent"]
    exe = CLAUDE_CMD or shutil.which("claude")
    with lock:
        a = agents[name]
        a.update(status="running", started_at=now_iso(), ended_at=None, cost_usd=None)
    if not exe:
        push_event(name, "error", "claude CLI를 찾을 수 없습니다.")
        with lock:
            agents[name].update(status="error", ended_at=now_iso())
        append_log(pipe, step, {"status": "중단", "open_issues": ["[확인필요] claude CLI 없음"]}, step["prompt"])
        return
    prefix = [sys.executable, "-X", "utf8", exe] if exe.lower().endswith(".py") else [exe]
    cmd = [*prefix, "-p", step["prompt"] + RUN_LOG_INSTRUCTION, "--agent", name,
           "--output-format", "stream-json", "--verbose", "--permission-mode", "default"]
    if step.get("allowed_tools"):
        cmd += ["--allowedTools", *step["allowed_tools"]]
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    push_event(name, "info", "에이전트를 시작했습니다.")
    try:
        p = subprocess.Popen(cmd, cwd=BASE, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, creationflags=flags)
    except OSError as e:
        push_event(name, "error", f"실행 실패: {e}")
        with lock:
            agents[name].update(status="error", ended_at=now_iso())
        return
    with lock:
        procs[name] = p
    deadline = time.time() + pipe.get("step_timeout_sec", 900)
    timer = threading.Timer(max(1, deadline - time.time()), lambda: kill_proc(p))
    timer.daemon = True
    timer.start()

    final_text, cost, is_error = None, None, False
    for raw in iter(p.stdout.readline, b""):
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            push_event(name, "raw", line)
            continue
        t = ev.get("type")
        if t == "assistant":
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") == "text" and c.get("text", "").strip():
                    txt = c["text"].strip()
                    shown = txt.split("RUN_LOG:")[0].strip() or "RUN_LOG 작성"
                    push_event(name, "text", shown.replace("\n", " ")[:300])
                elif c.get("type") == "tool_use":
                    push_event(name, "tool", summarize_tool(c.get("name", "tool"), c.get("input")))
        elif t == "user":
            for c in ev.get("message", {}).get("content", []) if isinstance(ev.get("message", {}).get("content"), list) else []:
                if c.get("type") == "tool_result" and c.get("is_error"):
                    body = c.get("content")
                    body = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
                    push_event(name, "warn", "도구 오류/거부: " + body[:200])
        elif t == "result":
            final_text, cost, is_error = ev.get("result"), ev.get("total_cost_usd"), bool(ev.get("is_error"))
    p.wait()
    timer.cancel()
    with lock:
        procs.pop(name, None)
        stopped = state["stop_requested"]
        timed_out = time.time() >= deadline
    part = extract_run_log(final_text) or {}
    if stopped:
        status, part = "stopped", {**part, "status": "중단", "open_issues": part.get("open_issues", []) + ["사용자가 대시보드에서 중지함"]}
    elif timed_out:
        status, part = "error", {**part, "status": "중단", "open_issues": part.get("open_issues", []) + [f"시간 초과({pipe.get('step_timeout_sec')}초)"]}
    elif is_error or p.returncode not in (0, None):
        status, part = "error", {**part, "status": part.get("status", "중단")}
    elif not part:
        status, part = "done", {"status": "일부", "open_issues": ["[확인필요] 에이전트가 RUN_LOG 줄을 출력하지 않음"],
                                "verification": {"method": "", "not_verified": ["에이전트 결과 요약: " + (final_text or "")[:500]]}}
    else:
        status = "done"
    run_id = append_log(pipe, step, part, step["prompt"])
    push_event(name, "info", f"run_log.jsonl에 {run_id} 기록 ({part.get('status')})")
    with lock:
        agents[name].update(status=status, ended_at=now_iso(), cost_usd=cost, last_run_id=run_id)


def kill_proc(p):
    if p.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    else:
        p.kill()


def pipeline_thread():
    pipe = load_pipeline()
    try:
        for gi, group in enumerate(pipe["groups"], 1):
            with lock:
                if state["stop_requested"]:
                    break
                state["message"] = f"{gi}/{len(pipe['groups'])} 단계 묶음 실행 중"
                for step in group:
                    agents[step["agent"]]["status"] = "queued"
            threads = [threading.Thread(target=run_step, args=(pipe, s), daemon=True) for s in group]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
    finally:
        with lock:
            for a in agents.values():
                if a["status"] == "queued":
                    a["status"] = "idle"
            state.update(running=False, ended_at=now_iso(),
                         message="중지됨" if state["stop_requested"] else "실행 완료")


def start_run():
    with lock:
        if state["running"]:
            return False, "이미 실행 중입니다."
        reset_agents(load_pipeline())
        state.update(running=True, stop_requested=False, started_at=now_iso(), ended_at=None, message="실행 시작")
    threading.Thread(target=pipeline_thread, daemon=True).start()
    return True, "실행을 시작했습니다."


def stop_run():
    with lock:
        if not state["running"]:
            return False, "실행 중이 아닙니다."
        state["stop_requested"] = True
        state["message"] = "중지 중…"
        running = list(procs.values())
    for p in running:
        kill_proc(p)
    return True, "중지를 요청했습니다."


# ---------- 차트·지적사항 ----------
_chart_cache = {"mtime": None, "data": None}


def chart_data():
    pipe = load_pipeline()
    path = os.path.join(BASE, pipe["model_file"])
    if not os.path.exists(path):
        return None
    m = os.path.getmtime(path)
    if _chart_cache["mtime"] == m:
        return _chart_cache["data"]
    try:
        import openpyxl
        ws = openpyxl.load_workbook(path, data_only=True, read_only=True)["손익"]
        cols = "BCDEFG"
        data = {"sheet": "손익", "bars": []}
        for c in cols:
            label = ws[f"{c}3"].value or c
            alt, _, scen = str(label).partition(" ")
            data["bars"].append({"cell": f"{c}12", "label": label, "alternative": alt, "scenario": scen,
                                 "value": ws[f"{c}12"].value, "breakeven": ws[f"{c}15"].value})
    except Exception as e:  # 시트 구조가 다르면 오류 메시지만 전달
        data = {"error": str(e)}
    _chart_cache.update(mtime=m, data=data)
    return data


def findings(rows):
    valid = [r for r in rows if not r.get("_invalid")]
    reviews = [r for r in valid if r.get("agent") == "reviewer" and r.get("findings")]
    if reviews:
        r = reviews[-1]
        return {"source": f"{r['run_id']} reviewer", "items": r["findings"]}
    items = []
    for r in valid:
        for c in r.get("checklist") or []:
            if isinstance(c, dict) and c.get("result") == "fail":
                items.append({"severity": "주의", "stage": f"{r.get('stage')}단계 {c.get('item', '')}",
                              "location": r.get("agent"), "problem": c.get("note") or c.get("item"), "suggestion": ""})
        for o in r.get("open_issues") or []:
            items.append({"severity": "개선", "stage": f"{r.get('stage')}단계", "location": r.get("agent"),
                          "problem": str(o), "suggestion": ""})
    return {"source": "체크리스트 fail·미해결 항목 (reviewer 기록 없음)" if items else None, "items": items}


def snapshot():
    rows = read_log()
    if not agents:
        reset_agents(load_pipeline())
    with lock:
        ag = [{**{k: v for k, v in a.items() if k != "events"}, "events": list(a["events"])} for a in agents.values()]
        st = dict(state)
    return {"state": st, "agents": ag, "log": rows, "chart": chart_data(), "findings": findings(rows),
            "server_time": now_iso()}


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/dashboard.html"):
            with open(HTML, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if self.path == "/api/state":
            return self._send(200, snapshot())
        self._send(404, {"error": "not found"})

    def do_POST(self):
        # 다른 사이트에서 몰래 실행하지 못하도록 사용자 정의 헤더를 요구(교차 출처 요청은 사전 검사에서 차단됨)
        if self.headers.get("X-Dashboard") != "1":
            return self._send(403, {"error": "forbidden"})
        if self.path == "/api/run":
            ok, msg = start_run()
            return self._send(200 if ok else 409, {"ok": ok, "message": msg})
        if self.path == "/api/stop":
            ok, msg = stop_run()
            return self._send(200 if ok else 409, {"ok": ok, "message": msg})
        self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    reset_agents(load_pipeline())
    print(f"대시보드: http://{HOST}:{PORT}  (종료: Ctrl+C)")
    print(f"로그 파일: {LOG}")
    print(f"에이전트 실행 파일: {CLAUDE_CMD or shutil.which('claude')}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
