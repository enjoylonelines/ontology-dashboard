# 서비스 수준 기반 DecisionSession/브리핑 큐 평가 — 2026-11-05

## 원문 기준
`docs/plans/engineering-foundations/03-scalability-evaluation.md`: 10초 감시, 100/500/1000 assets, low/medium/burst, 3회 반복, queue wait P50/P95, 최신 유효 briefing, snapshot consistency 및 중요 이벤트 누락 금지. 10초는 **watch interval**이며 AI 생성 완료 SLA가 아니다. 실제 critical P95, 일반 생성 P95, 복구 RTO, provider concurrency/cost 허용치 미확정.

## 재실행 시도 및 증거 경계
- 기존 `scripts/evaluate_briefing_scalability.py --repeats 3` 재실행은 과거 120개 provider 개별 row 파일 `tests/eval/results/agent_summary_llm_eval_live_120_20260905_pm_fix.json`이 현재 checkout에 없어 실패했다. 기존 결과 파일에는 provider aggregate p50=3904.235ms, p95=5788.544ms가 남아 있다.
- 따라서 `tests/personal_service_profile_queue_replay.py`에서 위 두 aggregate를 **19:1 비율의 합성 지연 샘플**로 만들어 기존 `challenger_projection`을 재사용했다. 과거 120개 샘플을 복원했다고 주장하지 않는다.
- 100/500/1000 × 1/10/50% × worker 2/4/8 = 27개 **결정론적 시뮬레이션**. 10초 × 6 cycle, 각 scenario 1회; 로컬 PostgreSQL, 실제 LLM, API, RLS 또는 실제 queue process를 실행하지 않았다.
- 결과: `docs/evidence/2026-11-05-service-profile-queue-replay.json`.

## 1,000대 핵심 결과
| 변화율 | Worker | 후보 이벤트 | 생성 | 병합 | queue wait P95 |
|---|---:|---:|---:|---:|---:|
| 1% | 8 | 60 | 60 | 0 | 3.904초 |
| 10% | 8 | 600 | 203 | 397 | 43.702초 |
| 50% | 8 | 3000 | 603 | 2397 | 234.427초 |

이 수치는 synthetic provider-latency discrete-event replay의 산출물이다. 생성 완료 시점이 6 cycle 창을 넘어가는 draining 구간도 포함된다. 따라서 실제 1,000대 지원/운영 SLO 위반을 입증하지 않는다. 병합은 최신 후보 교체이지 silent drop이 아니다. 실제 중요한 이벤트 누락 여부는 이 모델로 검증하지 못한다.

## 트레이드오프와 판단
1. **중요도/재생성 수요 우선:** 모든 상태 변화를 생성 큐로 보내면 medium/burst에서 provider backlog가 커진다. 중요 이벤트 우선 + 일반 이벤트 debounce/60초 제한 + 최신 후보 병합을 실서비스 정책 그대로 재현해야 한다. 다만 중요 이벤트를 coalesce하면 중간의 critical 전이를 누락할 수 있으므로 critical invariant 별도 검증.
2. **Worker 확장:** 병렬성 증가가 queue wait를 줄일 수 있지만 실제 provider 동시성 제한·rate limit·비용을 무시하면 낙관적이다. 2/4/8 mock과 제한된 실 provider 샘플을 분리한다.
3. **DB Polling vs RabbitMQ:** 메시지 전달 효율은 생성 처리 용량을 늘리지 않는다. PostgreSQL query/lock/CPU가 병목이라는 실측 전에는 브로커 도입 보류. 브로커 채택 시 outbox, 중복 delivery, retry/DLQ, tenant fairness 운영 비용까지 포함.
4. **테넌트 identity 등록:** 현재 identity별 DB polling은 규모가 커지면 빈 쿼리 비용이 증가한다. tenant-scoped batch claim 또는 합법적인 discovery 없이 전체 스캔은 금지.
5. **P0 correctness:** snapshot binding, mandatory evidence recall, latest valid briefing availability, 결과 중복 반영 금지. throughput 향상을 위해 정합성을 희생하지 않는다.

## 다음 실제 실험의 합격 Gate (미확정 SLO는 제안으로만 관리)
- Priority Critical vs Normal 별도 queue wait P50/P95와 E2E, critical 이벤트 누락 0, stale snapshot 최종 노출 0, 중복 결과 0.
- 기존 10초 감시 deadline miss 및 60초 일반 재생성 제한, 후보 발생/병합/실제 생성량 기록.
- 100/500/1000 assets × 1/10/50% × 3회, 최소 6개 watch cycle 이상, Worker 2/4/8, PostgreSQL query rate/lock wait/CPU, provider 제한·비용 계측.
- 실제 실행 중 worker SIGKILL 후 lease 만료/재시작 fencing, 복구 RTO.
- Queue wait P95 5초와 RTO 30초는 이전에 제안한 **임시 기준**이며 합의된 SLO로 간주하지 않는다.

**판단:** 지금은 메시지 브로커 도입보다 서비스 수준의 수요 제어·우선순위·측정 경계를 확정하는 것이 먼저다.
