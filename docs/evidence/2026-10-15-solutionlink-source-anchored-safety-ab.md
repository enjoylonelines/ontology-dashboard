# SolutionLink source-anchored 안전 처리 A/B

## 무엇을 보강했나

기존 16개 readiness fixture는 정책과 정답을 함께 작성한 synthetic contract다.
이번 suite는 이전 격리 실행에 사용한 Canonical V3.1 prediction timeline에서
compressor 6개·CNC 6개의 서로 다른 설비를 결정론적으로 고른 12개 source row를
고정했다. 원본 timeline SHA-256, upstream commit, 선택 규칙, 각 prediction ID를
manifest에 기록한다.

각 seed에는 하나의 정상 상태와 다섯 개의 decision hold mutation(evidence gap,
quality hold, stale, asset mismatch, missing artifact), 그리고 하나의 승인 계보 누락
mutation을 적용한다. 총 84개 case다.

## A/B 결과

동일 84개 case에서 artifact 존재만 보는 A와 현재 evidence-aware B를 비교했다.

| 측정 | A: artifact-only | B: evidence-aware | 변화 |
| --- | ---: | ---: | ---: |
| 조치 노출 F1 | 0.50 | 1.00 | +0.50 |
| hold 60건의 조치 노출 | 48/60 (80%) | 0/60 (0%) | **80%p 감소** |
| 정상/계보별 판단 가능 조치 24건 유지 | 24/24 | 24/24 | 유지 |
| 승인 계보 누락 12건 탐지 | 0/12 | 12/12 | +12건 |

재현 명령:

```bash
.venv/bin/python scripts/evaluate_solutionlink_source_anchored_ab.py \
  --source-timeline /path/to/prediction_timeline.jsonl \
  --output evaluation/results/solutionlink-source-anchored-safety-ab-v1.json
.venv/bin/python -m pytest -q tests/test_solutionlink_source_anchored_ab.py
```

## 신뢰성에서 좋아진 점과 남은 한계

좋아진 점은 선택한 seed가 정책 구현에서 임의로 만든 설비 ID가 아니라 버전·해시가
기록된 source timeline의 서로 다른 12개 설비라는 것이다. selection rule도
failure score나 기대 결과를 보지 않고 asset ID hash로 고정했다.

그러나 근거 결손은 실제 장애 표본이 아니라 선언된 mutation이고, 라벨은 independent
review가 아닌 self-label이다. 따라서 이 수치는 source-anchored synthetic safety
regression이며, 실제 운영 분포·사용자 판단·현장 효과의 A/B로 해석하지 않는다.
