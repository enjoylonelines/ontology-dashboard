# 2026-11-09 — 격리 PostgreSQL Decision Worker 500/1,000건 부하·복구 검증

## 범위

- 일회성 로컬 PostgreSQL 16 컨테이너(pgvector/pgvector:pg16), loopback 127.0.0.1:55439, database ontology
- 실제 migration 52개 적용
- deterministic synthetic packet/agent만 사용. 외부 LLM·유료 API·실제 설비 이벤트 수집은 사용하지 않음
- revision: e8268f1182cb8ff00d3e785daee60983da30f814 위에서 독립-worker load 도구의 count 상한만 1,000으로 확장한 미커밋 변경

## Human-owned fields

- Human hypothesis / Prediction: unrecorded
- Decision required: DB queue를 유지할지 또는 broker A/B을 시작할지에 대한 human decision pending
- Changed belief: unrecorded
- Falsification condition: 이 작은 합성 환경에서의 무누락 결과는 production SLO, 독립 제공자 지연, 다중 노드 동작을 증명하지 못한다.

## 실행 결과

### DB queue burst

tests.personal_decision_queue_load를 2/4 worker, 각 500/1,000 distinct asset으로 한 번씩 실행했다.

| 작업 | Worker | 전체 완료(초) | 처리량(건/초) | 등록 P50/P95(ms) | 누락 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 500 | 2 | 10.474 | 47.74 | 95.24 / 107.52 | 0 |
| 500 | 4 | 7.166 | 69.78 | 135.71 / 155.51 | 0 |
| 1,000 | 2 | 19.947 | 50.13 | 94.83 / 107.29 | 0 |
| 1,000 | 4 | 14.436 | 69.27 | 139.30 / 157.99 | 0 |

등록 지연은 queue wait가 아니며, worker 수를 늘렸을 때 등록 비용이 커지는 현상도 관측됐다.

### 독립 worker 강제 종료·재기동

tests.personal_decision_independent_worker_load가 별도 OS worker process를 시작하고, 제출 뒤 SIGKILL한 다음 새 process를 시작했다.

| 작업 | 제출(초) | 전체 완료(초) | 재기동부터 전체 완료(초) | 완료/누락 | 관측 E2E P50/P95(ms) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 500 | 5.000 | 13.918 | 8.913 | 500 / 0 | 6,369.94 / 8,650.69 |
| 1,000 | 10.246 | 26.438 | 16.187 | 1,000 / 0 | 11,144.45 / 15,976.00 |

관측 E2E 값은 poll 기반 상한이며 queue-wait 지표가 아니다.

### Focused PostgreSQL regression

tests/test_personal_decision_postgresql_queue.py 및 tests/test_personal_decision_pressure_recovery.py: **12 passed, 27.86s**.

원시 결과: docs/evidence/2026-11-09-decision-worker-postgres-burst-results.json, docs/evidence/2026-11-09-decision-worker-recovery-500.json, docs/evidence/2026-11-09-decision-worker-recovery-1000.json.

## 한계와 종료 상태

- 모든 조건은 한 번씩만 실행한 합성 workload다. 통계적 재현성, CPU/lock/connection-pool 분해, 지속 부하, production SLO는 측정하지 않았다.
- 독립 worker 재시작은 이 로컬 loopback DB와 등록된 identity scope에서만 검증됐다. 다중 노드·tenant discovery·provider rate limit은 미검증이다.
- P1의 500/1,000 burst 및 강제 종료 후 복구 확인 범위는 충족했다. broker 도입 또는 운영 채택 판단은 human decision pending으로 남긴다.
