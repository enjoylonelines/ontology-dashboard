import React from "react";
import { createRoot } from "react-dom/client";
import { FactoryOverview } from "../../src/features/operations/decision/DecisionWorkspaceApplication";
import type { OperationsAsset, OperationsBootstrapModel, OperationsEvent } from "../../src/features/operations/api/operationsContracts";
import "../../src/app.css";
import "../../src/features/operations/operations.css";

const observedAt = "2026-10-07T09:00:00Z";
const projectId = "manufacturing-demo-project";
const eventId = "EVT-SOLUTIONLINK-MAIN";
const targetAssetId = "CNC-S04-L04-01";
const provenance = { datasetId: "solutionlink-fixture", datasetVersionId: "solutionlink-fixture", datasetLabel: "촬영용 고정 입력", sourceVersion: null, modelVersion: "fixture-model", policyVersion: null, schemaVersion: null, promptVersion: null, sourceRefs: ["fixture-only"] };
const makeAsset = (assetId: string, displayName: string, line: string, status: OperationsAsset["status"], event: string | null): OperationsAsset => ({
  assetId, displayName, assetType: "cnc", site: line.slice(0, 3), line, cell: line, status, failureProbability: status === "critical" ? 0.82 : status === "warning" ? 0.62 : 0.08,
  confidence: "high", confidenceScore: 0.92, criticality: "high", assignedEngineer: "설비 담당", estimatedDowntimeMinutes: status === "critical" ? 120 : null,
  sparePartAvailable: null, predictedFailureType: status === "normal" ? "unknown" : "tool_wear", recommendedDecision: status === "normal" ? "continue_monitoring" : "request_inspection",
  observedAt, eventId: event, topFactors: [], riskHistory: [], sensorHistory: [], provenance,
});
const assets = [
  makeAsset("CNC-S01-L01-01", "1구역 · 1셀 · CNC 가공기 1", "S01-L01", "normal", null),
  makeAsset("CNC-S01-L03-02", "1구역 · 3셀 · CNC 가공기 2", "S01-L03", "warning", "EVT-S01-L03"),
  makeAsset("CNC-S02-L02-01", "2구역 · 2셀 · CNC 가공기 1", "S02-L02", "normal", null),
  makeAsset("CNC-S03-L01-03", "3구역 · 1셀 · CNC 가공기 3", "S03-L01", "attention", "EVT-S03-L01"),
  makeAsset("CNC-S03-L04-02", "3구역 · 4셀 · CNC 가공기 2", "S03-L04", "normal", null),
  makeAsset(targetAssetId, "4구역 · 4셀 · CNC 가공기 1", "S04-L04", "critical", eventId),
] satisfies OperationsAsset[];
const events: OperationsEvent[] = assets.filter((asset): asset is OperationsAsset & { eventId: string } => asset.eventId !== null).map(asset => ({
  eventId: asset.eventId, scenarioId: "solutionlink-fixture", assetId: asset.assetId, assetName: asset.displayName, line: asset.line, status: asset.status,
  failureProbability: asset.failureProbability, confidence: asset.confidence, predictedFailureType: asset.predictedFailureType, recommendedDecision: asset.recommendedDecision,
  criticality: asset.criticality, assignedEngineer: asset.assignedEngineer, estimatedDowntimeMinutes: asset.estimatedDowntimeMinutes, sparePartAvailable: asset.sparePartAvailable,
  observedAt, datasetVersionId: provenance.datasetVersionId, ontologyObjectId: null,
}));
const model = {
  context: { projectId, projectName: "솔루션링크 데모", workspaceId: "manufacturing-demo", workspaceName: "공장 A", datasetVersionId: provenance.datasetVersionId, datasetLabel: provenance.datasetLabel, sourceVersion: null, modelVersion: provenance.modelVersion, schemaVersion: null, sourceMode: "gold-fixture-fallback", sourceStatus: "fixture", observedAt, warnings: [] },
  assets, events, metrics: { totalAssets: assets.length, normal: 3, attention: 1, warning: 1, critical: 1, dataQualityHold: 0, averageRisk: 0.34, estimatedDowntimeMinutes: 120, pendingDecisions: 3 }, lineRisk: [], selectionRestoreError: null,
} as OperationsBootstrapModel;

function Preview() {
  const select = (assetId: string, selectedEventId: string | null) => {
    if (assetId === targetAssetId && selectedEventId === eventId) window.location.assign("./solutionlink-main-scenario-preview.html");
  };
  return <div className="dw-app"><main><FactoryOverview model={model} onSelect={select} /></main></div>;
}

createRoot(document.getElementById("root")!).render(<Preview/>);
