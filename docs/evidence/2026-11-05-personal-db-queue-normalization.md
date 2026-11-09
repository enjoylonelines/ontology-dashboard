# 개인 확장 DB 작업 큐 정상화 검증 — 2026-11-05

## 변경 범위
- `systems/backend/app/infra/db/decision_run_repository.py`: `list_pending` 조회 시 organization/project 외에 **identity_hash를 SQL WHERE에서 먼저 적용**, 이후 LIMIT. 서로 다른 설비가 첫 50건을 차지해 누락되는 복구 경계 수정.
- `systems/backend/app/operations/decision_session_service.py`: 동일 request_id/identity가 이미 lease를 보유하여 `DecisionRunBusy`가 발생하면 안정적인 session ID와 미완료 상태를 반환하고 **추가 Worker dispatch는 하지 않음**. API async 경로는 이 경우 기존 202 queued 응답과 Location을 제공.
- 새 메시지 브로커, Worker 프로세스 분리, 큐 인프라 추가 없음.

## 재현 및 검증
- 변경 전: `tests/test_personal_decision_pressure_recovery.py`에서 **3 passed, 2 failed**. 실패는 20개 동시 중복 요청의 `DecisionRunBusy`와 100개 미전달 작업 중 일부 미복구.
- 변경 후: `.venv/bin/python -m pytest -q -s -p no:cacheprovider tests/test_personal_decision_pressure_recovery.py tests/test_decision_durable_runner.py tests/test_decision_worker_supervisor.py tests/test_decision_session_api.py`
- 결과: **29 passed, 5 deprecation warnings in 27.51s**.
- 중복 제출: 20건 요청 → 고유 session ID 1개, Worker handle 1개, 최종 결과 저장.
- 저장 후 미전달: 서로 다른 설비 identity 100건 → **100/100 복구**, 로컬 elapsed **2.735s**.
- 10/30/100개 burst 각 3회 모두 완료. 100개 전체 완료 wall time: **2.874 / 3.060 / 2.826초**. 일회성 로컬 합성 수치이며 운영 SLO가 아님.

## 남은 검증 경계
- SQLite + deterministic synthetic agent + in-process 2 workers. PostgreSQL 경합/락과 다중 호스트 환경, 실제 LLM 호출, 센서 이벤트 수집 E2E는 미검증.
- 복구 테스트는 실제 프로세스 강제 종료가 아니라 **DB에 미전달 작업을 생성한 후 새 서비스가 명시적으로 resume**한 실험.
- `DECISION_RESUMER_IDENTITIES` 설정이 없으면 애플리케이션 시작 시 자동 resumer가 시작되지 않는 운영 설정 조건은 이번 수정에서 바꾸지 않았다.
- `list_pending`은 아직 identity별 limit을 두며, 같은 identity의 완료된 기록이 선두를 차지할 경우의 starvation 가능성은 추가 검증 필요.
- 팀 공유 원격에는 push하지 않았고, 커밋도 수행하지 않았다.
