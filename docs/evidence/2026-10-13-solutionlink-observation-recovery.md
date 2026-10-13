# SolutionLink 관측 갱신과 판단 결과 재검토 경로

## 해결하려는 문제

설비 판단의 입력 근거가 오래되었거나 필수 데이터가 빠진 경우, 기존 판단을 새 조치에 그대로 쓰거나 그럴듯한 설명을 노출하면 안 된다. 반대로 새 관측이 들어온 뒤에는 사용자가 이전 판단과 새 판단을 혼동하지 않고, 근거가 갱신된 결과를 검토할 수 있어야 한다.

이 문서는 로컬 데모의 계약과 UI 동작을 기록한다. 실제 공장 운영, 실제 고장 데이터, 외부 LLM 품질 또는 운영 성과를 증명하는 문서가 아니다.

## 구현한 흐름

```text
오래된 판단 / 근거 부족
  -> Decision Workspace: 새 관측 수집 대기, 새 조치 차단
  -> local Generator overlay batch
  -> runtime overlay observation/event 저장
  -> Generator runtime enqueue
  -> /internal/prediction-results 검증 및 inbox 수신
  -> append-only runtime Product Result 생성
  -> operations bootstrap이 최신 eventId를 자산에 반영
  -> Decision Workspace: 기존 판단 보존 + 새 관측 반영됨
  -> 사용자가 "새 판단 결과 확인"을 눌러 새 revision을 명시적으로 검토
```

핵심은 새 결과가 이전 선택을 조용히 덮어쓰지 않는다는 점이다. 선택 중인 이벤트와 자산의 최신 `eventId`가 다를 때에만 새 revision 안내와 이동 버튼을 제공한다. 최신 관측이 아직 없을 때는 기존 판단을 새 조치에 사용하지 않는다고 안내한다.

## 화면 계약

| 상태 | 사용자에게 보이는 내용 | 허용되는 다음 행동 |
| --- | --- | --- |
| stale / data-quality hold | `새 관측 수집 대기`와 현재 판단의 새 조치 사용 중단 | 관측·필수 근거 도착을 기다린 뒤 새 결과 검토 |
| 새 Product Result 생성됨 | `새 관측 반영됨`, 기존 판단 보존 안내 | `새 판단 결과 확인`으로 명시적으로 이동 |
| 현재 결과가 최신 | 갱신 배너 없음 | 현재 근거 범위 안에서 검토 |

자연어 브리핑은 현재 snapshot hash와 근거 freshness가 일치할 때만 노출되는 기존 게이트를 유지한다. 따라서 "LLM 응답 준비 중"으로 오래된 근거를 포장하지 않는다.

## 이번에 확인한 회귀 범위

2026-10-13 로컬 환경에서 아래 검증을 통과했다.

- backend 경계 계약 71개 통과: runtime overlay output, Generator enqueue, prediction-result inbox, live maintenance runtime.
- frontend lint 통과.
- Decision recovery 상태 단위 테스트 3개: stale 대기, 새 revision 명시, 최신 결과 무표시.
- 기존 DecisionProposalPanel 테스트를 포함한 Vitest 38개 통과.
- Chromium에서 stale 근거/검증 실패 fixture를 주입한 failure-boundary E2E 1개 통과. 이 경로는 새 조치 사용 중단과 새 관측 대기 문구를 직접 확인한다.

이는 소스 계약과 로컬 브라우저 경계에 대한 회귀 증거다. 아직 local Generator worker를 실제로 기동해 한 batch가 DB에 적재되고 새 결과가 화면에 도착하는 시간을 계측하거나, 여러 자산에서 성공률을 집계한 결과는 없다. 따라서 회복률, 지연시간, 실제 설비 품질 수치를 주장하지 않는다.

## 다음 계측을 위한 기준

실제 local worker 경로를 준비한 뒤에만 다음 수치를 추가한다.

1. stale 상태에서 새 결과까지의 처리 시간: overlay batch 수신 시각부터 새 revision 노출 시각까지.
2. 회복 완료율: 유효 batch 중 검증을 통과해 새 Product Result까지 생성된 비율.
3. 안전 차단율: stale/근거부족 fixture가 조치 가능 상태나 자연어 브리핑으로 노출되지 않은 비율.
4. 보존성: 새 결과가 발생해도 기존 event/result artifact가 변경되지 않은 비율.

각 수치는 fixture, 실행 커밋, batch 수, 실패 사유를 함께 기록하며, synthetic/local 결과로만 표기한다.

## 재현 명령

```bash
.venv/bin/pytest -q \
  tests/test_runtime_overlay_output_contract.py \
  tests/test_runtime_overlay_generator_enqueue.py \
  tests/test_prediction_result_inbox.py \
  tests/test_live_predictive_maintenance.py

cd systems/frontend
npm run lint
npx vitest run \
  src/features/operations/decision/decisionRecovery.test.ts \
  src/features/operations/decision/DecisionProposalPanel.test.tsx
npx playwright test e2e/solutionlink-live-failure-boundary.spec.ts \
  --project=chromium --reporter=line
```
