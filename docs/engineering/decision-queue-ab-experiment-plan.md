# DB 큐 vs 메시지 브로커 A/B 실험 준비 — 2026-11-05

## 목적
현재 DB 기반 DecisionSession 큐의 신뢰성/지연 한계를 먼저 계측하고, **동일한 durable result store 및 작업 로직**을 사용하는 메시지 브로커 구성과 공정하게 비교한다. 메시지 브로커 도입은 결론이 아니라 검증할 가설이다.

## 이번 구현
- `systems/backend/app/operations/decision_worker_process.py`: 별도 HTTP 서버 없이 실행하는 전용 DB polling worker 진입점. `python -m app.operations.decision_worker_process` (backend import 경로/환경 설정 필요). SIGINT/SIGTERM에 graceful stop.
- `DECISION_RESUMER_IDENTITIES` 필수: identity provider 없이 전체 DB를 무제한 스캔하지 않는다. 테넌트 RLS 범위를 명시적으로 등록한 경우에만 복구.
- `DecisionSessionApplicationService.resume`: 반복 tick에서 동일 session에 대해 중복 Worker dispatch하지 않도록 프로세스 내 in-flight handle 공유.
- `tests/test_personal_decision_pressure_recovery.py`: 연속 resume tick의 동일 job 재사용과 scope 미설정 시 전용 Worker 기동 거부 검증.
- 로컬 명령: `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_personal_decision_pressure_recovery.py tests/test_decision_worker_supervisor.py tests/test_decision_durable_runner.py`
- **25 passed in 28.28s**. 기존 PostgreSQL 통합 테스트는 이전 단계에서 통과했으나 이번 변경 이후 재실행하지 않았으므로 별도 회귀가 필요.

## 아직 수행하지 않은 작업
1. **실제 독립 프로세스 E2E:** API가 작업을 등록하고 별도 worker 프로세스가 처리하는 흐름, SIGKILL/재시작 및 lease 만료 후 복구, 작업 유실·최종 결과 중복 확인.
2. **PostgreSQL 부하 계측:** 100/500/1,000건 burst + 지속 유입, 큐 대기 P50/P95, end-to-end 완료 지연, 처리량, DB lock/CPU, worker 2/4/8 확장 효과. 측정 전 서비스 수준 목표 확정 필요.
3. **자동 발견:** `DECISION_RESUMER_IDENTITIES` 미설정 상태의 안전한 tenant-scoped discovery는 미구현. 현재는 등록된 identity만 poll.
4. **A/B 구현:** RabbitMQ 등 브로커 기반 소비자, 동일 작업 ID/저장소/재시도 정책 및 동일 부하 실험 미구현.

## 비교 가설과 중단 조건
- DB 기반 큐가 요구 지연·복구 시간·처리량을 충족하면 브로커 도입을 보류한다.
- 지속적인 DB claim/poll 경합 또는 작업 분배 지연이 명확한 병목일 때만 RabbitMQ 실험을 진행한다.
- 브로커는 작업 실행 능력을 증가시키지 않으며, 전달/소비 분리의 운영 비용을 함께 평가해야 한다.
- 현 단계의 합성 테스트 통과를 실서비스 SLO나 독립 프로세스 안정성으로 해석하지 않는다.

## 보존/배포
개인 브랜치 `codex/solutionlink-evidence-flow`; 기존 README 수정과 미커밋 문서 보존. 팀 원격에는 push하지 않음.
