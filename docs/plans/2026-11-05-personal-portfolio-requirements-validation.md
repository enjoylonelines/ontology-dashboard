# 개인 확장: 요구사항 기반 검증 계획 (초안, 2026-11-05)

## 현재 상태와 출처
- 로컬 checkout: `/Users/hb/Projects/ontology-dashboard`; HEAD `1369d2ca716db959e9e3ed1e1cf54d0a50521473`; branch `codex/solutionlink-evidence-flow`.
- 팀 저장소 remote: `origin` (`Biz-CollabCraft/ontology_dashboard`); 개인 포크 remote: `personal` (`enjoylonelines/ontology-dashboard`).
- 로컬 remote-tracking `personal/main` = `1369d2ca`, `origin/main` = `7a465fb5`; 로컬 참조 기준 개인 포크 main은 팀 main보다 54 commits 앞서며 반대 방향 0. 원격 최신 상태는 fetch 없이 미확인.
- `README.md`는 작업 시작 전부터 수정되어 있었으므로 이 계획 작업에서 변경하지 않는다.
- 이 문서는 기존 팀 구현을 개인 단독 성과로 재분류하지 않는다. 개인 확장 결과는 이후 별도 commit/evidence로 구분한다.

## Project charter
**목적:** 제조 설비의 합성 예측·운영 이벤트를 기반으로, 근거가 확인된 위험 설명과 사람의 조치 검토를 지원하는 AI 시스템을 요구사항 중심으로 검증한다.

**포함:** 근거-판단 일치, 근거 부족 시 보류, 이벤트·작업 멱등성, Worker 중단/재시작, 성능 및 품질 측정.
**제외:** 실제 공장 운영 성과, 실제 고장 예측 정확도, 정비비 절감 입증, 사전 근거 없는 Kubernetes/Kafka 도입.

## Problem framing
- Observed: 기존 코드에 `DecisionWorkerSupervisor(max_workers=2)`가 `decision_session_service.py`에서 생성되며, durable runner에 claim/evidence binding 로직이 존재한다. 이것만으로 장애 복구의 성공/실패를 판정할 수 없다.
- Human hypothesis: 사용자가 명시한 방향은 '합성 데이터 환경에서는 운영 문제 해결 주장보다 시스템 요구사항을 재정의하고 검증하는 것이 방어에 유리하다'이다.
- Prediction: unrecorded.
- Falsification: 정의된 입력·중단 조건에서 결과의 근거 불일치, 중복 반영, 유실이 관측되면 해당 요구사항 미충족.
- Decision required: 세 실험 중 첫 대표 문제 선택, 허용할 작업량과 수용 기준 승인.
- Stop condition / Budget: pending human decision.
- Unknowns: 최신 원격 SHA, 기존 테스트의 현재 통과 여부, Worker 분리의 실측 효과, 독립 라벨 데이터 확보 가능성.

## 우선 요구사항 및 수용 증거
| ID | 우선 | 요구사항 | 검증 방식 | 상태 |
|---|---|---|---|---|
| FR-01 | P0 | 결과·설비·시점·Evidence 식별자를 연결 | 고정 fixture 및 불일치 mutation | 기존 증거 재검토 필요 |
| FR-02 | P0 | 누락/오래된 근거로 조치를 생성하지 않음 | safety A/B, hold case | 기존 합성 평가 존재; 재실행 필요 |
| NFR-01 | P0 | 같은 요청/이벤트의 최종 결과 중복 반영 방지 | 동시 중복 제출·결과 카운트 | 미검증 |
| NFR-02 | P0 | Worker 중단 뒤 유실 없이 복구 또는 명시적 실패 | kill/restart, lease expiry, stale write | 기존 테스트 존재; 재실행 필요 |
| NFR-03 | P1 | AI 설명의 근거 충실도·누락·보류 품질 측정 | held-out 평가, 근거 없는 주장 집계 | 독립 라벨 검증 필요 |
| NFR-04 | P1 | 부하 변화에 따른 처리량·P95·자원 사용 측정 | 동일 fixture, Worker 수 통제 | 미측정 |
| FR-03 | P1 | 사람의 승인·보류·이력 추적 | API 상태 전이/감사 기록 | 기존 구현·테스트 확인 필요 |

## 판별 실험 후보 (구현 전 baseline 확인)
1. **Evidence/AI 품질:** 기존 파이프라인 대 최소 변경 challenger. 고정된 평가 세트와 독립 held-out 사례를 구분해 필수 근거 recall, unsupported claim, abstention, 비용/지연을 측정. self-label mutation은 독립 품질 증거로 주장하지 않는다.
2. **Durable execution:** 현재 API 내부 Supervisor + durable runner 대 최소 변경 challenger(예: dispatch/recovery 경계 보강). API 중단 직후, Worker kill, lease 만료, 중복 요청을 주입하고 terminal state, 중복 반영, 복구 시간, stale write를 확인. 이미 충족하면 재설계하지 않는다.
3. **확장성:** 기존 단일 구성에서 동시 요청 수를 변화시키며 throughput/P95/CPU/memory/queue depth를 측정. Worker 독립 서비스나 다중 서버는 병목이 입증된 뒤 검토.

## 진행 게이트
1. 현재 `README.md` 미커밋 변경을 보존하고 remote 최신 상태를 확인한다.
2. 기존 관련 테스트와 평가 스크립트의 실행 가능성·결과를 기록한다.
3. 가장 중요한 **하나의** 대표 문제에 대해 baseline/challenger, fixture, invariant, 중단 기준을 승인받는다.
4. 작은 판별 실험을 실행하고 `docs/evidence/`에 revision, 명령, 원시 증거, 한계를 남긴다.
5. 사람의 채택/보류/기각 판단 전에는 설계 전환을 완료로 표시하지 않는다.

## 포트폴리오 주장 경계
- **팀 프로젝트:** 공동 설계/구현 및 당시 개인 담당 영역을 별도로 기재한다.
- **개인 확장:** 포크의 이후 독립 변경·실험·측정만 본인 확장 성과로 기재한다.
- 합성 fixture의 테스트 통과는 실제 제조 현장 효용이나 운영 SLO를 증명하지 않는다.
