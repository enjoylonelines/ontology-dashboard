# Evaluation Results

자동 생성되는 평가 결과는 기본적으로 Git에서 제외한다.

추적할 결과는 다음 조건을 만족해야 한다.

- 재현 가능한 실행 명령이 있다.
- 사용한 데이터·모델·임계값 버전이 기록돼 있다.
- Gold 시나리오 ID와 연결된다.
- 민감정보가 포함되지 않는다.
- 최종 발표 또는 릴리즈 근거로 승인됐다.

권장 결과 범주:

- 모델 지표와 임계값 비교
- Evidence 추적률
- 리포트 수치 일치율
- 역할 적합성 평가
- UI Gold flow 결과
- LLM fallback 성공률

## Tracked Recommendation Policy v1 Artifact

`recommendation-policy-v1.json`은 PR #96 계획에 따른 Gold v1 synthetic evaluation/demo
fixture store 결과다.

- 재현 명령: `PYTHONPATH=systems/backend:. python3 scripts/seed_gold_recommendations.py --output evaluation/results/recommendation-policy-v1.json`
- 검증 명령: `PYTHONPATH=systems/backend:. python3 scripts/evaluate_gold.py --root .`
- 최근 로컬 검증: targeted backend suite 70개 통과, Gold runner 8/8 통과,
  operational recommendation/Decision/WorkOrder/Maintenance side effect 0건
- 범위: Gold 8/8 engineering acceptance, policy/source lineage, replay/no-op,
  policy-v2 별도 evaluation artifact, 새 Product Result revision lineage,
  runtime/imported writer boundary
- 미검증: PostgreSQL production E2E, 실제 정비 승인 UI, 자동 정비 실행,
  현장 정비 효과, 비용/RPN 최적화, LLM 기반 추천 결정

이 artifact는 운영 추천 테이블 seed가 아니다. `fixture_recommendations[*].store`는
`evaluation_demo_fixture`이고, `do_not_operationalize=true`로 고정된다. Gold 8/8은
engineering acceptance evidence일 뿐 현장 효과나 비용 절감 증거가 아니다.

## Tracked SolutionLink Readiness Gold v1 Artifact

`solutionlink-readiness-gold-v1.json`은 의사결정 화면의 최신성·근거 보류·작업
이력 연결을 확인하는 16개 합성 계약 fixture 결과다.

- 재현 명령: `python3 scripts/evaluate_solutionlink_readiness.py --root . --output evaluation/results/solutionlink-readiness-gold-v1.json`
- 검증 명령: `pytest -q tests/test_solutionlink_readiness_evaluation.py`
- 측정값: ready/hold 판정 정밀도·재현율·F1, 보류 상태의 조치 노출률,
  lifecycle별 필수 lineage link 완전성 및 누락 탐지
- 범위: 고정된 합성 contract-regression. 라이브 DB를 바꾸거나 API/작업지시를 쓰지 않는다.
- 미검증: 실제 source outage, LLM 품질, 사용자 과업 시간·오류, 정비 결과,
  비용·가동중단·RPN 효과

## Tracked Canonical Replay Cohort v1 Artifact

`solutionlink-canonical-replay-cohort-v1.json`은 로컬 Canonical V3.1의 고정
40-artifact cohort을 읽기 전용으로 재생한 결과다. historical as-of에서는 reference
완전성·provenance·version consistency를, fixed-current as-of에서는 stale 차단을
동시에 확인한다. 합성 replay이므로 held-out ML 성능이나 현장 효과로 사용하지 않는다.

## Tracked Canonical Priority Replay v1 Artifact

`solutionlink-canonical-priority-replay-v1.json`은 runtime에서 분리된
Canonical V3.1 evaluation truth와 LOSO prediction timeline을 checksum 검증 후
읽어, 같은 시점의 후보 설비 중 Top-K 우선순위가 다음 24시간 고장 설비를 얼마나
포착하는지 재현한다.

- 재현 명령: `python3 scripts/evaluate_solutionlink_priority_replay.py --package-root /path/to/predictive_maintenance_canonical_v3.1 --output evaluation/results/solutionlink-canonical-priority-replay-v1.json`
- 측정값: package checksum 14/14, candidate window 690, Top-5 precision 26.61%,
  recall 51.23%, Top-10 precision 15.68%, recall 60.38%
- 범위: local synthetic package의 offline, leave-one-site-out priority replay
- 미검증: live factory accuracy, 정비 예방·비용·다운타임 효과, 작업지시 자동화,
  사용자 과업 성과

## Live Failure-boundary Browser E2E

`systems/frontend/e2e/solutionlink-live-failure-boundary.spec.ts`는 로그인된
리팩터링 Decision Workspace에서 selected Case의 stale·근거 gap·LLM validation hold·
lineage 누락을 주입하는 Chromium E2E다. stale이면 새 조치가 숨겨지고, 검증 실패한
LLM prose가 표시되지 않으며, activity 없는 승인 상태가 `점검 시작 대기`로 표시되지
않는지를 확인한다. 이 주입은 외부 사용자 테스트나 provider/live factory 검증이 아니다.
