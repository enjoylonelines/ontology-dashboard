# 개인 확장 10/30/100 Burst 및 복구 경계 탐색 — 2026-11-05

## 실행 조건
- Revision: `1369d2ca716db959e9e3ed1e1cf54d0a50521473`; dirty checkout (기존 README 변경 및 신규 개인 실험 파일).
- Test: `tests/test_personal_decision_pressure_recovery.py`
- Command: `.venv/bin/python -m pytest -q -s -p no:cacheprovider tests/test_personal_decision_pressure_recovery.py`
- Python 3.12.14, pytest 9.1.1; SQLite isolated DB, deterministic synthetic agent, 10 submitter threads / 2 worker threads, no external provider.
- **첫 실행: 3 passed, 2 failed in 16.96s.** 실패를 숨기지 않고 아래 기록.

## 3회 반복된 정상 burst
| 고유 설비 수 | enqueue (s) | 전체 완료 (s) |
|---|---|---|
| 10 | 0.427 / 0.379 / 0.416 | 0.473 / 0.410 / 0.447 |
| 30 | 0.470 / 0.921 / 1.106 | 0.969 / 1.007 / 1.196 |
| 100 | 1.440 / 1.258 / 1.328 | 2.504 / 2.590 / 2.453 |

각 반복에서 고유 세션 수, 저장된 결과, 설비 연결을 검증. 수치는 해당 로컬 합성 환경의 wall time이며 E2E 운영 지연이나 P95가 아님.

## 실패 1 — 동일 요청 20개 동시 제출
- `test_same_request_concurrent_retries_converge_to_one_persisted_run`에서 `DecisionRunBusy('decision_run_in_progress')` 예외 발생.
- 원인 경계: `DecisionRunRepository.claim()`은 활성 lease가 있는 동일 실행에 Busy를 발생시킨다. `operations/router.py`는 이 예외를 HTTP **409**로 매핑한다.
- 이는 DB 중복 실행 차단의 실패를 의미하지 않지만, 동시 중복 요청 모두가 202/기존 세션 반환으로 수렴한다는 기대는 충족하지 않는다. 클라이언트 409 retry 경로와 eventual completion은 별도 검증 필요.

## 실패 2 — 100개 저장 후 미전달 작업 복구
- `test_100_persisted_before_dispatch_are_resumed_by_fresh_service`에서 일부 state의 `result`가 None으로 남음.
- `DecisionRunRepository.list_pending(identity, limit=50)`는 tenant/project 단위로 **상위 50건**을 조회한 뒤 `DecisionSessionApplicationService.resume_pending()`가 정확히 동일한 identity만 필터링한다. 100개 설비 identity로 호출할 때 첫 50건 바깥에 있는 작업은 해당 방식으로 도달하지 못할 수 있다.
- `dependencies.decision_resumer_identity_provider()`는 `DECISION_RESUMER_IDENTITIES` 환경변수가 없으면 None을 반환하고, `main.py`는 provider가 있는 경우에만 자동 resumer를 시작한다. 기본 자동 복구가 항상 실행된다고 주장할 수 없다.
- 이 실험은 **프로세스를 실제 kill하지 않고**, DB에 queued 상태를 만든 뒤 새 service에서 명시적으로 `resume_pending`을 호출했다. 실서비스의 자동 복구를 직접 검증한 것이 아니다.

## 판정
- 정상 합성 burst: 관측된 조건에서 통과.
- 동시 동일 요청의 응답 수렴: 기존 API가 409를 반환하므로 기대를 다시 정의해야 함.
- 다수 설비의 미전달 작업 복구: 현재 tenant-scoped first-50 조회 + exact identity 필터의 불일치가 발견됨. 재현 테스트가 실패함.
- Human hypothesis/prediction/decision/changed belief: unrecorded / pending human decision.
- 다음 최소 변경 후보: `list_pending`에서 identity_hash 조건을 SQL로 필터링한 뒤 limit 적용; resumer identity discovery/운영 설정은 별도 설계 결정. 변경 전후 동일 실패 테스트로 비교하고 PostgreSQL 계약도 점검.
- 이번 실행에서 프로덕션 코드는 수정하지 않았고 커밋/푸시하지 않았다.
