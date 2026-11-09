# DecisionSession DB 작업 큐 정상화 및 PostgreSQL 검증 (2026-11-05)

## 배경과 문제
개인 확장 실험에서 100개 고유 설비의 합성 DecisionSession은 완료됐으나, 동일 request_id의 동시 제출에서 `DecisionRunBusy`가 노출됐고, 100개 미전달 작업을 복구할 때 일부가 누락됐다. 별도 브로커 도입 전에 기존 DB 기반 작업 큐의 정합성·복구를 먼저 정상화했다.

## 변경사항
1. **정확한 대기 작업 조회:** `DecisionRunRepository.list_pending`에서 organization/project뿐 아니라 `identity_hash`를 SQL WHERE에 포함해 LIMIT 50 이전에 대상 identity를 제한한다. 기존에는 프로젝트 내 다른 설비가 상위 50건을 차지할 수 있었다.
2. **동일 요청의 동시 재전송:** `DecisionSessionApplicationService.enqueue`에서 동일 프로세스의 진행 중 session ID를 in-flight handle로 공유해 중복 dispatch를 억제한다. 다른 프로세스가 lease를 점유하면 Busy를 잡아 동일 session ID와 미완료 상태를 반환한다. 클라이언트는 Location의 GET으로 완료를 확인한다. 실행 완료된 handle은 다음 enqueue 시 정리한다.
3. **기존 durable execution 유지:** PostgreSQL/SQLite의 Claim, lease/fencing, state 저장 및 supervisor/resumer를 유지한다. 별도 메시지 브로커를 추가하지 않는다.

## 검증 방법 및 결과
- 재현 이전: 10/30/100개 정상 burst × 3회 통과, 20개 동일 요청 및 100개 미전달 복구 테스트 실패(3 passed / 2 failed).
- 최초 수정 후 SQLite 중심 회귀: 29 passed.
- 추가 PostgreSQL 실험 중 첫 실행에서 **중복 dispatch race 발견**: 동시 enqueue가 DB claim을 release한 후 worker가 claim하기 전 중복 worker를 제출할 수 있었다. in-flight coalescing으로 수정 후 재검증.
- PostgreSQL 16 disposable Docker (`pgvector/pgvector:pg16`, loopback port 55439), 52개 migration 적용. 별도 DB에서 `DECISION_TEST_POSTGRES_DSN` 지정하여 테스트.
- 명령: `DECISION_TEST_POSTGRES_DSN=<isolated postgres DSN> .venv/bin/python -m pytest -q -s -p no:cacheprovider tests/test_personal_decision_postgresql_queue.py tests/test_personal_decision_pressure_recovery.py tests/test_decision_worker_supervisor.py tests/test_decision_durable_runner.py tests/test_decision_session_api.py`
- 결과: **32 passed, 5 existing deprecation warnings, 39.50s**.
- PostgreSQL: 20개 동시 동일 요청 → 세션 1개/최종 결과 존재. PostgreSQL 미전달 100건 → 100건 모두 복구.
- SQLite: 10/30/100개 고유 설비 × 3회 통과, 20개 동시 재전송 → 세션 1개, 100개 미전달 → 100개 복구. 신규 테스트에서 단일 고유 worker job ID 조건도 확인.
- SQLite에서 **새 서비스의 configured identity provider**로 Resumer 시작 후 100건 자동 완료 확인. 이는 실제 OS process kill이 아닌 새 서비스 인스턴스 재생성 테스트이다.

## 운영 경계와 남은 과제
- **무설정 자동 발견 미구현:** `DECISION_RESUMER_IDENTITIES` 환경변수가 없으면 현재 애플리케이션 startup은 resumer를 시작하지 않는다. 다중 테넌트의 모든 미완료 identity를 무권한으로 스캔하는 방식은 RLS 경계를 훼손할 수 있으므로 추가하지 않았다. 실제 운영에서는 인증된 tenant/project scope discovery 또는 관리되는 등록 메커니즘을 설계해야 한다. 자동 복구 검증은 identity provider가 등록된 범위에 한정된다.
- `list_pending`의 identity별 limit과 완료된 state의 조회 순서에 따른 starvation, 다중 서버/다중 worker 프로세스, 실제 kill 후 PostgreSQL 재시작, provider 지연 및 LLM rate limit은 추가 검증 필요.
- 동일 프로세스의 중복 요청은 in-flight handle을 공유하지만, 다중 프로세스는 기존 DB lease fencing에 의존하며 202 + GET polling 계약을 따른다.
- 합성 packet/agent로 검증했으므로 실설비 이벤트 수집 E2E, 실제 AI 품질, 운영 SLO/P95에 대한 주장 불가.

## 의사결정
기존 DB 작업 큐를 유지하고 실제 운영 요건 및 PostgreSQL 경합 지표를 측정한 뒤 메시지 브로커 도입 여부를 판단한다. 사용자 고유의 변경된 판단/중단 조건은 아직 미기록.

## 변경 파일
- `systems/backend/app/infra/db/decision_run_repository.py`
- `systems/backend/app/operations/decision_session_service.py`
- `tests/test_personal_decision_pressure_recovery.py`
- `tests/test_personal_decision_postgresql_queue.py`
- `docs/evidence/2026-11-05-personal-db-queue-normalization.md`
- `docs/evidence/2026-11-05-personal-pressure-recovery-findings.md`

개인 브랜치 `codex/solutionlink-evidence-flow`에서 검증. 팀 공유 원격에는 push하지 않음.
