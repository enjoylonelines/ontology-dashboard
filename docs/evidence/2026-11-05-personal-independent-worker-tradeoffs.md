# 독립 프로세스 DB Worker 복구·유입 부하 실험 및 트레이드오프 — 2026-11-05

## 검증 환경
- 로컬 격리 PostgreSQL 16 Docker, 52 migrations, deterministic synthetic agent/packet. 별도 OS subprocess worker (`tests/personal_decision_worker_harness.py`)와 생산자 프로세스 (`tests/personal_decision_independent_worker_load.py`).
- 100개 설비 identity, 목표 유입 20건/s, 0.1초 poll interval, worker process 강제 SIGKILL 후 재시작.
- **주의:** 생산자에서 작업을 모두 저장한 후 SIGKILL하므로 실제 실행 중 작업을 죽였는지 확인하지 않았다. lease 만료를 기다려서 진행 중인 상태를 복구하는 시나리오의 증거는 아니다.
- 독립 worker harness는 실제 production dependency가 아닌 합성 agent를 주입한다. production worker 진입점의 실제 runtime packet loader 통합 테스트는 별도 필요.
- DB에 이미 저장된 작업만 대상으로 하며 HTTP API를 통한 요청은 아니다.

## 관측 결과
`DECISION_TEST_POSTGRES_DSN=<isolated loopback DSN> DECISION_LOAD_COUNT=100 DECISION_LOAD_RATE=20 .venv/bin/python -m tests.personal_decision_independent_worker_load`

- 제출 100건, 목표 유입 20건/s, producer elapsed 5.011s
- 전체 완료 100/100, 누락 0건, 전체 elapsed 8.278s
- SIGKILL 시점부터 재시작 Worker로 전체 완료까지 3.264s
- 관측 요청 후 완료 P50 2669.97ms, P95 4733.85ms (100ms 간격 polling 관측 상한 포함)
- 원본: `docs/evidence/2026-11-05-personal-independent-worker-load.json`
- 각 조건 1회, 통계적 신뢰 구간 없음. queue wait P95, PostgreSQL CPU/lock wait, 실행 중 프로세스 kill 여부는 **미측정**.

## 설계 트레이드오프

| 선택 | 장점 | 비용·위험 | 현재 판단 |
|---|---|---|---|
| PostgreSQL 상태+polling 큐 | 저장소 1개, 기존 lease/fencing 및 RLS 재사용, 운영 단순 | polling DB read 증가, 등록 identity 수만큼 조회, DB 트랜잭션 경합 | 비교 기준 유지 |
| 독립 Worker 프로세스 | API와 실행 자원 분리, 장애 독립성 | 배포/환경변수/health check 추가, identity 등록 관리 | 제한된 범위에서 실험 완료 |
| RabbitMQ + PostgreSQL 결과 저장 | 이벤트 전달/consumer 확장·backpressure 도구, polling 감소 가능 | 브로커 추가 운영, publish-commit 원자성 문제, at-least-once 중복, DLQ/재전송/관측 필요 | 병목 확인 전 보류 |
| Outbox + RabbitMQ | DB commit과 publish 사이 유실 창 완화 | outbox relay, 청소·재시도·모니터링 복잡도 증가 | 브로커 도입 시 비교에 포함 |
| 높은 Worker 병렬성 | 처리량 증가 가능 | LLM/API rate limit, DB connection/lock 경합, 비용 증가 | 2/4/8에서 계측 후 결정 |
| 짧은 polling interval | 작업 발견 지연 감소 | DB query/CPU 증가, 빈 조회 증가 | 0.1/1/5초 비용 비교 필요 |
| 명시적 identity 등록 | RLS 범위 명확, 무단 cross-tenant scan 방지 | 신규 설비/identity 누락 시 작업 영구 미발견 | 안전한 scope discovery 설계 필요 |

## 발견한 구조적 위험
- `resume_pending`은 **identity별 SELECT**를 수행한다. 100개 identity를 0.1초마다 검사하면 유휴 시에도 많은 DB query가 발생할 수 있다. 실제 query count는 미계측. 향후 tenant/project 범위의 RLS-aware batch claim 및 인덱스/limit 검증이 우선이다.
- 완료된 state가 `list_pending`의 LIMIT 50 안에 남을 수 있어 같은 identity의 미완료 작업을 가릴 위험이 있다. SQL에서 `result IS NULL`을 선필터링하는 migration/index 전략 검토 필요.
- `DecisionResumer`는 callback exception을 삼키므로 운영 로그·실패 카운터·health signal 필요.
- `DecisionSessionApplicationService`의 in-flight 중복 억제는 프로세스 내부에만 적용된다. 다중 프로세스에서는 DB lease/fencing으로 최종 결과를 보호하지만 중복 dispatch 비용은 발생 가능.
- queue wait와 execution time을 분리하는 `queued_at/started_at/completed_at` 계측, 100/500/1000 지속 부하 반복, API P95, DB lock wait/CPU, 실제 in-flight SIGKILL 테스트가 아직 필요하다.

## 판단 및 중단 조건
현재 데이터로 RabbitMQ가 DB 큐보다 빠르거나 안전하다고 결론 내릴 수 없다. 다음 단계는 (1) 실제 실행 중인 작업 SIGKILL/lease-expiry 검증, (2) 유휴 polling 비용 및 DB 경합 측정, (3) queue wait P95 분리, (4) 같은 워크로드에서 DB 큐와 RabbitMQ 비교. DB 큐가 사전 합의된 지연·복구·비용 목표를 충족하면 브로커는 도입하지 않는다.

개인 브랜치에서만 변경, 팀 remote push 없음.
