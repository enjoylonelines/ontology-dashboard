# 개인 확장 Baseline 검증 기록 — 2026-11-05

## 재현 정보
- Checkout: `/Users/hb/Projects/ontology-dashboard`
- Branch: `codex/solutionlink-evidence-flow`
- HEAD: `1369d2ca716db959e9e3ed1e1cf54d0a50521473`
- 실행 전부터 미커밋 `README.md`가 있었고 `docs/plans/2026-11-05-personal-portfolio-requirements-validation.md`가 미추적 파일이었다. 따라서 이번 결과는 **깨끗한 커밋만을 대상으로 한 증거는 아님**.
- Python 3.12.14 / pytest 9.1.1 / 로컬 `.venv`.
- 실행 명령:
  ```sh
  .venv/bin/python -m pytest -q -p no:cacheprovider \
    tests/test_decision_durable_runner.py \
    tests/test_decision_worker_supervisor.py \
    tests/test_decision_session_api.py \
    tests/test_solutionlink_readiness_evaluation.py \
    tests/test_solutionlink_readiness_ab_evaluation.py \
    tests/test_solutionlink_source_anchored_ab.py
  ```
- 결과: **27 passed, 5 warnings in 11.15s** (실행 로그 확인). 경고에는 FastAPI on_event deprecation 및 Starlette anyio alias deprecation이 포함됨.

## 검증한 것과 하지 않은 것
- SQLite 기반 `test_real_process_kill_sqlite`는 별도 자식 프로세스를 강제 종료하고 재실행해 회복을 검사하는 기존 테스트이며 이번 suite에 포함됐다.
- Lease 만료 뒤 오래된 token으로 저장을 거부하는 fencing, 요청 재사용, Supervisor 재시작/대기 실행 및 Session API의 승인 경계 관련 회귀 테스트가 포함됐다.
- 합성 readiness 16-case suite와 source-anchored 12-seed/84-scenario suite의 기존 기대값에 대한 회귀 테스트가 통과했다. Source-anchored 테스트의 기대값은 hold 60건 중 baseline action 노출 48건, treatment 0건; ready 24건 유지; 깨진 계보 12건 탐지.
- 이 결과는 **기존 테스트/자체 정의 fixture가 코드의 기대조건을 통과했다**는 사실만 의미한다. 별도 독립 정답 라벨, 실제 공장 사용자, 실제 운영 장애 통계, PostgreSQL 멀티 프로세스 부하, multi-host, 처리량/P95는 검증하지 않았다.
- 외부 LLM API를 호출하는 평가 실험은 수행하지 않았다.

## 관측된 문제와 다음 판별
- 현재 suite에서 실패는 관측되지 않았다. Worker 구조를 즉시 교체할 근거 없음.
- AI/challenger hypothesis: API 프로세스와 in-process Supervisor가 연결된 상태에서 프로세스 종료 직전 dispatch가 누락될 수 있는지 구체적인 crash window 검사로 구분할 가치가 있다. 기존 resumer가 이를 해결할 수 있으므로 결함이라고 단정하지 않는다.
- 대안 1: 기존 runner/resumer 그대로 유지.
- 대안 2: 최소한의 enqueue/dispatch/recovery 경계 보강. 
- 최소 실험: request persisted 이후 submit 이전의 프로세스 중단을 고정 fixture로 재현하고 새로운 프로세스에서 terminal state 도달, 중복 결과 반영 없음, 회복 시간/실패 상태를 확인.
- Human hypothesis/prediction/최종 채택 판단: 미기록 / pending human decision.
- Stop condition/budget: 다음 실험 전에 확정. 이번 검증은 6개 파일의 기존 로컬 회귀 테스트 재실행에서 종료.
- 기존 `README.md`와 팀 원본은 변경하지 않았고 커밋/푸시도 하지 않았다.
