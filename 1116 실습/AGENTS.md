# AGENTS.md

이 폴더의 엑셀 모델(`market_model_case_student.xlsx`)과 그것을 바탕으로 한 계획서·결과보고서를 작성할 때 지키는 규칙입니다.

## 기획 절차 (필수)

사업 기획·타당성 분석·계획서·보고서 작업을 할 때는 **항상 아래 기획절차서를 기준으로 진행**한다.

@playbook.md

- 작업을 시작할 때 지금 요청이 playbook의 몇 단계(0~13단계)에 해당하는지 먼저 밝히고, 그 단계의 **① 무엇을 구하는가 · ② 필요한 입력 · ③ 타당성 확인**을 따른다.
- 앞 단계의 산출물이 없으면 건너뛰지 말고, 빠진 단계를 알린 뒤 [확인필요]로 표시한다.
- 단계를 마칠 때는 그 단계의 ③ 타당성 확인 체크리스트 결과를 함께 보고한다.
- 단계별 담당 서브 에이전트는 playbook 부록 B를 따른다(`.Codex/agents/`).

## 계획서·결과보고서 작성 규칙

1. 계획서의 모든 숫자는 엑셀에서 가져와야 한다.
2. '가정' 시트에서 구분이 '가정'인 값을 쓸 때에는 결과보고서 내용에도 '가정'이라고 밝힌다.
3. 엑셀에 없는 내용은 지어내지 말고 [확인필요]라고 표시한다.
4. 불리한 숫자를 빼거나 낙관 시나리오만 적용하는 것은 안 된다.
5. 결론은 '가', '부', '조건부 시행' 중 하나로 도출한다.

## 엑셀 작업 규칙

- 자료 수집 시에는 값, 기준 시점, 출처, URL을 함께 기재하고, 못 찾는 경우에는 '미확인'으로 남긴다.
- 가정은 보수/기준/낙관 세 값으로 제안한다.
- 계산은 반드시 수식을 걸어서 계산한다.

## 실행 로그 규칙 (`run_log.jsonl`)

- playbook의 단계 작업을 마칠 때마다(완료·일부 완료·중단 모두) 이 폴더의 `run_log.jsonl`에 실행 기록을 **한 줄 추가**한다. 서브 에이전트가 수행한 단계도 메인 세션이 기록한다.
- 형식은 **JSON Lines**: 한 줄 = 기록 1건 = 완전한 JSON 객체 하나. 줄바꿈 없이 한 줄로 쓰고, 파일 전체를 감싸는 배열이나 객체는 두지 않는다. UTF-8, 줄 끝은 `\n`.
- 파일 끝에 **추가(append)만** 한다. 기존 줄은 수정·삭제하지 않는다. 정정이 필요하면 새 줄을 남기고 `corrects`에 정정 대상 `run_id`를 적는다.
- 파일이 없으면 새로 만든다. `run_id`는 마지막 줄의 번호에 1을 더한다(`R0001`, `R0002` …).
- 추가한 뒤 마지막 줄이 JSON으로 읽히는지 확인한다(예: `python -I -X utf8 -c "import json;[json.loads(l) for l in open('run_log.jsonl',encoding='utf-8')]"`).
- 시각은 한국 시간 ISO 8601 형식(`2026-11-16T14:30:00+09:00`)으로 적는다.
- 숫자 값은 엑셀 셀에서 읽은 값을 그대로 적고 셀 위치를 함께 남긴다. 확인하지 못한 내용은 `"[확인필요]"` 또는 `"미확인"`으로 적는다.
- 입력 파일에는 **SHA-256 해시**를 남겨, 어느 버전의 파일로 작업했는지 확인할 수 있게 한다.
- 11단계(판정) 기록에는 `decision`을 반드시 채운다. 다른 단계에서는 `null`로 둔다.
- 대시보드(`dashboard_server.py`)로 실행하면 에이전트가 마지막 줄에 `RUN_LOG: {...}`를 출력하고, 서버가 `run_id`·`timestamp`·`inputs`(SHA-256 포함)·`parent_run_id`를 채워 추가한다. 중지·시간 초과도 `status: "중단"`으로 기록된다.

### 필드

| 필드 | 내용 |
|---|---|
| `run_id`, `timestamp` | 기록 번호, 한국 시간 |
| `project`, `model_file` | 사업 이름, 엑셀 파일명 (줄마다 반복해 각 줄이 단독으로 읽히게 함) |
| `stage`, `stage_name`, `agent`, `status` | playbook 단계 번호·이름, 수행 주체(main 또는 에이전트 이름), `완료`·`일부`·`중단` |
| `request`, `parent_run_id`, `corrects` | 요청 요약, 이어지는 이전 기록, 정정 대상 기록(없으면 `null`) |
| `inputs` | `files`(경로·수정 시각·sha256), `depends_on_stages`(바탕이 된 앞 단계) |
| `changes` | 파일·시트·셀·수정 전·수정 후·이유 |
| `sources` | 항목·값·단위·기준 시점·출처·URL·`확인`/`추정`/`미확인` |
| `assumptions_used` | 시트·셀·항목·구분(자료/가정/설정/계산)·보수/기준/낙관 값 |
| `outputs` | 지표·대안·시나리오·값·단위·시트·셀 |
| `checklist` | playbook ③ 항목별 `pass`/`fail`/`n/a`와 메모 |
| `decision` | 11단계만: `result`(가/부/조건부 시행), `criteria`(0단계 판정 기준별 충족 여부), `conditions`(조건부일 때 조건·기한) |
| `findings` | 12단계(reviewer)만: 지적 사항 배열 `{severity: 치명/주의/개선, stage, location, problem, suggestion}`. 대시보드 '검토 지적사항'에 표시됨 |
| `open_issues` | [확인필요] 항목 |
| `verification` | 검증 방법, 검증하지 못한 부분 |
| `backup`, `next_step` | 백업 파일 경로(없으면 `null`), 다음 단계와 담당 에이전트 |

### 한 줄 예시

```jsonl
{"run_id":"R0001","timestamp":"2026-11-16T14:30:00+09:00","project":"사업 이름","model_file":"엑셀 파일명","stage":3,"stage_name":"자료 수집","agent":"researcher","status":"완료","request":"요청 요약","parent_run_id":null,"corrects":null,"inputs":{"files":[{"path":"파일명","modified":"2026-11-16T10:24:00+09:00","sha256":"해시값"}],"depends_on_stages":[0]},"changes":[{"file":"파일명","sheet":"자료","cell":"B12","before":"10000000","after":"=B11/B43","reason":"변경 이유"}],"sources":[{"item":"항목","value":0,"unit":"단위","as_of":"기준 시점","source":"출처","url":"URL","status":"확인"}],"assumptions_used":[{"sheet":"가정","cell":"D7","item":"항목","category":"가정","values":{"보수":0,"기준":0,"낙관":0}}],"outputs":[{"name":"월 영업손익","alternative":"B안","scenario":"기준","value":0,"unit":"원","sheet":"손익","cell":"F12"}],"checklist":[{"item":"playbook ③ 체크 항목","result":"pass","note":""}],"decision":null,"open_issues":["[확인필요] 항목"],"verification":{"method":"검증 방법","not_verified":["검증하지 못한 부분"]},"backup":null,"next_step":"다음 단계와 담당 에이전트"}
```

11단계 `decision` 예시: `"decision":{"result":"조건부 시행","criteria":[{"criterion":"기준 시나리오 월 영업이익 > 0","met":false,"evidence":"손익!F12"}],"conditions":[{"condition":"파일럿 3개월 일 주문 271건 이상","deadline":"2027-03-31"}]}`
