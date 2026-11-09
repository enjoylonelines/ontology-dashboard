# PostgreSQL DecisionSession 부하 실험 — 2026-11-05

## 범위
격리된 PostgreSQL 16 (`pgvector/pgvector:pg16`, localhost:55439), 52개 migration, 합성 packet 및 deterministic agent. 기존 DB 작업 저장 + 프로세스 내부 Worker supervisor를 사용한 **burst** 실험. Worker 수 2/4, 각 100/500/1000개의 서로 다른 설비 identity. 각 조건 1회 실행, 전체 3,200개 결과 누락 0건. 실험은 실제 LLM이나 센서 수집 E2E가 아님.

## 재현
`DECISION_TEST_POSTGRES_DSN=<loopback disposable migrated PostgreSQL DSN> .venv/bin/python -m tests.personal_decision_queue_load`

코드: `tests/personal_decision_queue_load.py`
원시 결과: `docs/evidence/2026-11-05-personal-postgres-load-results.json`

| 작업 | Worker | 등록 완료(초) | 전체 완료(초) | 처리량(건/초) | 등록 지연 P50(ms) | 등록 지연 P95(ms) | 누락 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 2 | 1.289 | 2.315 | 43.19 | 103.72 | 259.65 | 0 |
| 100 | 4 | 1.453 | 1.597 | 62.63 | 142.37 | 164.76 | 0 |
| 500 | 2 | 5.745 | 10.995 | 45.47 | 104.91 | 169.89 | 0 |
| 500 | 4 | 6.832 | 7.024 | 71.18 | 134.84 | 153.18 | 0 |
| 1000 | 2 | 9.576 | 19.545 | 51.16 | 93.74 | 111.46 | 0 |
| 1000 | 4 | 14.245 | 14.692 | 68.06 | 139.48 | 160.28 | 0 |

## 해석
- 1,000건에서 Worker 2→4로 늘리면 관측 처리량 51.16→68.06건/초(약 +33%). 하지만 등록 완료 시간은 9.576→14.245초로 증가.
- 등록 지연 P95는 **queue wait P95가 아니다**. 작업 실행 시작 시각/완료 시각을 별도로 계측하지 않았으며, 동시 실행과 DB connection pool 경합을 분해하지 않았다.
- 각 조건 1회이므로 통계적 유의성/재현성 주장 불가. 모든 작업이 정상 저장된 것은 확인했지만 운영 SLO는 미검증.
- 프로세스 내부 Worker 실행이며 별도 OS 프로세스/프로세스 kill/restart 실험이 아니다. DB lock wait, PostgreSQL CPU, buffer 및 polling overhead도 미계측.
- 메시지 브로커 도입을 정당화할 증거는 **아직 없다**. 다음 단계는 독립 프로세스 DB polling E2E, 장애 주입, 지속 부하 및 P95 queue wait 계측. 동일 조건 RabbitMQ와 A/B 비교는 그 다음.

## 안전성
테스트는 임시 Docker PostgreSQL에서만 수행. 팀 원격 push/commit 없음.
