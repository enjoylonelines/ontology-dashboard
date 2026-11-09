# 100개 설비 DecisionSession 동시성 Baseline — 2026-11-05

## 환경과 범위
- Revision: `1369d2ca716db959e9e3ed1e1cf54d0a50521473`, branch `codex/solutionlink-evidence-flow`; 기존 미커밋 `README.md`와 신규 문서가 있는 dirty checkout.
- Test: `tests/test_personal_100_asset_decision_burst.py`.
- Command: `.venv/bin/python -m pytest -q -s -p no:cacheprovider tests/test_personal_100_asset_decision_burst.py`
- Local Python 3.12.14 / pytest 9.1.1; SQLite isolated tmp_path DB; 100 unique asset identities, 10 concurrent submitter threads, default 2 worker threads, fixed deterministic synthetic packet/agent, no external LLM calls.
- This is **100 DecisionSession requests for distinct assets**, not 100 raw sensor events through ingestor/generator nor 100 concurrent LLM calls.

## 결과
- **1 passed in 3.76s**.
- Enqueue completion: **0.614s** (one local run).
- All 100 futures completed: **2.641s** from start (one local run).
- 100 distinct session IDs; 100 persisted/readable sessions; each returned asset matches requested asset; cross-asset reads rejected.
- No P95, CPU, memory, DB wait, queue depth, provider latency or repetition-based confidence interval measured. The above timings are **not** operational SLO or scalable throughput estimates.

## 해석과 한계
- 현 구현이 해당 합성 100개 요청 burst를 로컬 SQLite/2-worker 조건에서 통과했다는 회귀 증거다.
- `DecisionSessionApplicationService.enqueue`가 등록한 작업의 처리만 검증한다. 실제 설비 이벤트 → 예측 결과 → 근거 생성 → DecisionSession 생성의 전체 흐름은 연결하지 않았다.
- 고유 요청 100개에 대한 정합성은 검증했지만 동일 요청의 동시 중복, 중간 Worker 강제 종료, PostgreSQL 경합, 재시작 후 유실 방지, AI 응답 품질은 이 실험에서 검증하지 않았다.
- AI/challenger hypotheses: 동일한 identity/request_id를 동시 제출하면 중복 dispatch는 발생할 수 있지만 durable run claim/fencing으로 최종 중복 결과를 막을 가능성이 있다. 이는 미검증 후보이지 관측된 결함이 아니다.
- Human prediction/decision/changed belief: unrecorded / pending human decision.
- 다음 판별 실험 후보: 동일 요청 10~20개 동시 재전송 + Worker 강제 종료/재시작을 포함해 DB 최종 결과 중복/유실을 검증. 별도 실행 예산 및 stop condition은 사람 결정 필요.
- 팀 공동 저장소 원격에는 push하지 않았다.
