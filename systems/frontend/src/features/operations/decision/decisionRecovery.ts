import type { OperationsAsset, OperationsEvent, OperationsEventDetailModel } from "../api/operationsContracts";

export type DecisionRecoveryState =
  | { kind: "waiting_for_observation"; title: string; detail: string }
  | { kind: "new_revision_available"; title: string; detail: string; eventId: string }
  | { kind: "none" };

/** A new Product Result is an explicit review revision, never a silent overwrite. */
export function decisionRecoveryState(
  detail: OperationsEventDetailModel,
  selectedEvent: OperationsEvent,
  latestAsset: OperationsAsset | null,
): DecisionRecoveryState {
  if (latestAsset?.eventId && latestAsset.eventId !== selectedEvent.eventId) {
    return {
      kind: "new_revision_available",
      title: "새 관측 반영됨",
      detail: "기존 판단은 보존했습니다. 새 근거로 만든 판단 결과를 확인해 주세요.",
      eventId: latestAsset.eventId,
    };
  }
  if (detail.assetDetailStatus?.isStale || detail.assetDetailStatus?.isDataQualityHold || detail.evidenceContext?.temporalStatus === "stale") {
    return {
      kind: "waiting_for_observation",
      title: "새 관측 수집 대기",
      detail: "현재 판단은 새 조치에 사용하지 않습니다. 새 관측과 필수 근거가 도착하면 새 판단 결과로 다시 검토할 수 있습니다.",
    };
  }
  return { kind: "none" };
}
