# SolutionLink 불완전 운영 근거 안전 처리 A/B — 2026-10-15

## 질문

최신성·근거 gap·품질 hold·설비 불일치·lifecycle 계보를 확인하지 않고
artifact 존재만으로 조치를 보이면, 현재 evidence-aware gate는 고정된 위험
시나리오에서 얼마나 많은 부적격 조치 노출을 막는가?

## 비교 설계

동일한 `solutionlink-readiness-gold-v1`의 16개 합성 시나리오를 사용했다.

- **A — artifact_presence_only_v0:** `artifact_id`가 있으면 조치를 노출한다.
  최신성, evidence gap, 품질 hold, 요청 설비 일치, lifecycle 계보는 확인하지 않는다.
- **B — evidence_aware_gate_v1:** 현재 readiness 계약을 적용한다. 필수 근거,
  24시간 최신성, 품질 hold, evidence gap, 설비 일치, lifecycle별 필수 link를 확인한다.

A는 과거 배포본을 복원한 것이 아니라, 검증을 생략한 표시 정책을 명시한
**반사실 baseline**이다. 따라서 “실서비스 개선율”이 아니라 정책 안전성의
contract-regression 비교다.

## 결과

| 측정값 | A: artifact-only | B: evidence-aware | 변화 |
| --- | ---: | ---: | ---: |
| 조치 노출 판정 F1 | 0.75 | 1.00 | +0.25 |
| 보류해야 하는 7건에서 조치 노출 | 6/7 (85.71%) | 0/7 (0%) | **85.71%p 감소** |
| 유효 조치 9건 유지 | 9/9 | 9/9 | 유지 |
| 깨진 lifecycle 계보 6건 탐지 | 0/6 | 6/6 | **100%p 증가** |

재현:

```bash
python3 scripts/evaluate_solutionlink_readiness_ab.py --root . \
  --output evaluation/results/solutionlink-readiness-safety-ab-v1.json
pytest -q tests/test_solutionlink_readiness_ab_evaluation.py
```

## 해석과 한계

이 수치는 “근거가 불완전한데도 조치가 노출되는 위험”을 고정 fixture에서
얼마나 줄이는지를 보여 준다. LLM 응답 품질, 실제 source outage, 현장 고장,
사용자 의사결정 시간, 지연시간, 비용·가동중단 효과는 측정하지 않는다.

포트폴리오에는 다음처럼만 쓴다.

> 고정된 16개 합성 운영 근거 시나리오에서, 근거 존재만 확인하는 기준선 대비
> evidence-aware gate는 부적격 조치 노출을 6/7건에서 0/7건으로 줄였고,
> 유효 조치 9건은 모두 유지했다.
