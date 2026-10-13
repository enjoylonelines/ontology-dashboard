# SolutionLink runtime overlay bridge 로컬 측정

## 질문

정비 완료 이벤트가 새 관측 batch로 바뀌고 Backend가 이를 읽을 수 있는가? 이 구간의 로컬 처리 시간은 어느 정도인가?

첫 번째 표본 표는 이 질문에만 답한다. 뒤의 full-path 실행은 Generator 전달과 Backend Product Result 수신까지를 별도로 기록한다. 브라우저에서 새 revision이 사람이 읽을 수 있게 표시되는 시간은 아직 측정하지 않았다.

## 고정 입력과 실행 환경

- ontology-dashboard commit: `8b7056b6`을 기준으로 실행했다. 측정 도구 보정은 이 실행 뒤 작업 트리에만 남아 있다.
- upstream source: `Biz-CollabCraft/gen_data` `main` at `2dc3a3f1f4cf0345a5b300b8d6965c6fa46eb363`.
- team source는 `/private/tmp`의 shallow clone으로 읽기 전용 사용했다.
- 각 표본은 독립된 temporary SQLite DB와 JSONL inbox/output root에서 실행했다.
- workload: maintenance lifecycle 3개 이벤트, gen_data 5 tick, 대상 설비 `CNC-S01-L01-01`.

실행 도구는 `scripts/smoke_runtime_overlay_local_bridge.py`다. 기존의 "availability event 1개" 기대값은 현 gen_data main의 반복 batch 발행과 맞지 않아, 다음 불변식으로 보정했다.

- availability event는 1개 이상이며 event ID가 고유하다.
- event ID는 동일 maintenance post-branch를 가리킨다.
- Backend reader가 읽은 event 수는 producer가 발행한 수와 같다.
- 모든 batch는 비어 있지 않다.
- dispatcher 재실행은 inbox에 중복 lifecycle event를 추가하지 않는다.

## 결과: 5회 로컬 표본

| 구간 | 평균 | 최소–최대 |
| --- | ---: | ---: |
| outbox → replay inbox | 1,484.22 ms | 1,455.00–1,529.30 ms |
| replay inbox → overlay availability | 707.63 ms | 690.44–718.37 ms |
| overlay reader | 48.78 ms | 45.36–53.48 ms |
| idempotency re-drain | 805.13 ms | 791.31–821.68 ms |
| 전체 smoke | **3,045.76 ms** | **2,987.30–3,097.32 ms** |

모든 표본에서 다음이 확인됐다.

- lifecycle outbox 3개는 첫 drain에 모두 처리됐고, 재실행에는 0개가 처리됐다.
- gen_data는 5 tick 동안 target 장비를 canonical source replay에서 제외하고, overlay availability 5개를 발행했다.
- 첫 availability는 fast-forward history 36 rows, 이후 4개는 새 tick당 1 row였다. 총 40 rows이며, Backend reader는 5개 event를 모두 읽었다.

## 해석과 한계

여기서 3.05초는 service HTTP latency나 사용자 응답 시간이 아니다. 임시 SQLite·JSONL, subprocess 기반 dispatcher와 FastAPI TestClient를 포함한 **로컬 bridge smoke wall time**이다. 특히 dispatcher와 gen_data process 기동 비용이 포함되어 있으므로 개별 운영 요청의 SLO로 사용하지 않는다.

이 결과가 보여 주는 것은 오래된 "단일 batch" 측정 가정이 아니라, 최신 gen_data가 append-only 관측 batch를 반복 발행해도 Backend reader가 각 batch를 빠짐없이 읽는다는 점이다. 새 Product Result/새 revision UI 노출 성공률은 아직 측정하지 않았다.

## full-path 격리 실행: 1회 CNC 양성 흐름

별도 session root와 일회성 PostgreSQL 컨테이너에서 실제 API lifecycle을 한 번 실행했다. 이 실행의 source package는 `gen_data` main `2dc3a3f1`에서 로컬로 재생성한 ZIP이다. 즉, source revision은 고정했지만 외부에 배포된 release archive를 그대로 재사용한 결과는 아니다.

```text
maintenance outbox
  -> gen_data overlay availability
  -> Generator queue/inference
  -> /internal/prediction-results
  -> append-only Product Result
  -> operations bootstrap
  -> Decision Workspace 새 판단 결과 확인
```

### 경로와 결과

대상은 `CNC-S02-L04-02`였고, API로 `inspection 요청 → 현장 접수/시작/완료 → TOOL_REPLACEMENT 권고/결정 → work order 승인 → 정비 시작/완료 → replay 요청`을 순서대로 완료했다.

- 완료 maintenance event: `MAINTENANCE-EVENT-9cbc6478-86b0-5175-94fc-22ee3a02ad49`
- gen_data overlay: 첫 post batch 36 rows + 이후 1-row batch 3개를 발행했다.
- Generator: 이 maintenance event를 계보로 갖는 최근 4개 run이 모두 `succeeded`였고, preprocessing·feature·prediction·batch build·delivery가 모두 성공했다. 각 run의 Generator 내부 시작→완료 시간은 63.99–69.14 ms였다. `prediction_delivery_status`는 모두 `sent`였다.
- Backend: `/results/latest`에서 위 maintenance event 계보를 가진 최신 Product Result 1건을 찾았고, `/results/post-maintenance`도 같은 result artifact를 반환했다. 반환된 artifact는 `RESULT#GEN-2d38bcf3-ae0f-5686-ae5b-ec19cc006476`이며 `overlay_branch_id`, `maintenance_action_id`, `maintenance_event_id`, `state_version=3`을 보존한다.

이 확인으로 아래 경로는 1회 통과했다.

```text
완료 정비 이벤트
  -> overlay 관측 batch
  -> Generator 예측/HTTP delivery
  -> append-only Product Result
  -> post-maintenance 결과 조회
```

### 음성 대조

동일한 `TOOL_REPLACEMENT`를 compressor 대상으로 요청했을 때 upstream gen_data가 `TOOL_REPLACEMENT is only valid for CNC equipment`로 거절했다. 이 실패는 우회하지 않았다. 잘못된 설비-정비 조합이 overlay 관측이나 결과로 조용히 승격되지 않는 fail-closed 경계의 확인이다.

### 해석과 남은 측정

이 full-path 실행은 **합성 데이터·격리 DB·단일 성공 표본**이다. 따라서 성공률, p50/p95, 사용자 의사결정 시간, 실제 고장 탐지율 또는 운영 SLO를 주장하지 않는다. 또한 Generator 내부 64–69 ms는 end-to-end 요청 시간도 아니다.

다음 단계는 동일 격리 환경에서 최소 5회 반복해 batch 수·delivery 수·Product Result 수·명시적 revision 전환 UI 노출을 함께 계수하는 것이다. 그 전까지 포트폴리오에는 “정비 후 최신 관측을 새 결과로 연결하는 전 구간을 1회 격리 실행으로 검증”이라고만 쓴다.

화면 코드의 분기 자체는 `decisionRecovery.test.ts` 3개 테스트로 회귀 검증했다. stale 상태에는 `새 관측 수집 대기`, 더 최신 결과가 있으면 사용자가 선택하는 `새 판단 결과 확인`을 렌더링하며, 현재 revision에는 recovery 문구를 보이지 않는 계약이다. 이는 브라우저 실사용 노출 시간 또는 사용성 검증을 대체하지 않는다.

## 재현

```bash
# gen_data main을 임시 clone한 뒤 requirements-lock.txt로 격리 venv를 준비한다.
.venv/bin/python scripts/smoke_runtime_overlay_local_bridge.py \
  --gen-data-root /private/tmp/solutionlink-gen-data-measurement \
  --work-root /private/tmp/solutionlink-overlay-measurement/run-1
```
