import { describe, expect, it } from "vitest";
import { decisionRecoveryState } from "./decisionRecovery";
import type { OperationsAsset, OperationsEvent, OperationsEventDetailModel } from "../api/operationsContracts";

const event = { eventId: "RESULT#stale", assetId: "CNC-1" } as OperationsEvent;
const asset = (eventId: string | null): OperationsAsset => ({ assetId: "CNC-1", eventId } as OperationsAsset);
const detail = (overrides: Partial<OperationsEventDetailModel> = {}) => ({
  assetDetailStatus: { isStale: false, isDataQualityHold: false },
  evidenceContext: { temporalStatus: "current" },
  ...overrides,
}) as OperationsEventDetailModel;

describe("decision recovery state", () => {
  it("holds the selected judgment while fresh observation is unavailable", () => {
    expect(decisionRecoveryState(detail({ assetDetailStatus: { isStale: true } as never }), event, asset("RESULT#stale"))).toMatchObject({ kind: "waiting_for_observation", title: "새 관측 수집 대기" });
  });
  it("requires an explicit move to a newer revision", () => {
    expect(decisionRecoveryState(detail({ assetDetailStatus: { isStale: true } as never }), event, asset("RESULT#fresh"))).toMatchObject({ kind: "new_revision_available", eventId: "RESULT#fresh" });
  });
  it("does not show recovery messaging for a current revision", () => {
    expect(decisionRecoveryState(detail(), event, asset("RESULT#stale"))).toEqual({ kind: "none" });
  });
});
