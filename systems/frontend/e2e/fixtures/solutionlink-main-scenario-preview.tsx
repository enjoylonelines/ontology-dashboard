import React from "react";
import { createRoot } from "react-dom/client";
import { ProductionRequestBoard } from "../../src/features/operations/overview/ProductionRequestBoard";
import { DisplayPreferencesProvider } from "../../src/ui/foundry/displayPreferences";
import "../../src/app.css";
import "../../src/features/operations/operations.css";

const assetId = "CNC-S04-L04-01";
const eventId = "EVT-SOLUTIONLINK-MAIN";
const projectId = "manufacturing-demo-project";
const workspaceId = "manufacturing-demo";
const asset = { assetId, displayName: "4구역 · 4셀 · CNC 가공기 1", assetType: "cnc", site: "공장 A", line: "S04", cell: "S04-L04", status: "critical", failureProbability: 0.82, confidence: "high", criticality: "high", assignedEngineer: "설비 담당", estimatedDowntimeMinutes: 120, predictedFailureType: "tool_wear", observedAt: "2026-10-07T09:00:00Z", eventId, topFactors: [{ id: "wear", feature: "tool_wear_min", label: "공구 마모", value: 230, unit: "min", contribution: 0.82, direction: "risk_up" }], riskHistory: [{ value: 0.46, observedAt: "2026-10-07T07:00:00Z" }, { value: 0.65, observedAt: "2026-10-07T08:00:00Z" }, { value: 0.82, observedAt: "2026-10-07T09:00:00Z" }], sensorHistory: [] };
const order = { work_order_id: "inspection-solutionlink-001", asset_id: assetId, event_id: eventId, equipment_id: assetId, asset_type: "cnc", work_type: "inspection", status: "approved", assigned_to: "maintenance", assigned_to_display_name: "보전 담당", created_at: "2026-10-07T08:30:00Z", inspection_result: null };
const coordination = { work_order_id: order.work_order_id, asset_id: assetId, event_id: eventId, request_id: "solutionlink-request-001", status: "pending", work_order_status: "approved", request: { work_summary: "공구 체결부 점검", downtime_minutes: 120, affected_items: "가공 품목", note: "생산 일정 대조 필요" }, requested_by: "maintenance", requested_by_name: "보전 담당", requested_at: "2026-10-07T08:30:00Z", response: null, responded_at: null, responded_by: null, responded_by_name: null };
const detail = { asset: { asset_id: assetId, display_name: asset.displayName, observed_at: asset.observedAt }, snapshot_basis: { asset_id: assetId, event_id: eventId, observed_at: asset.observedAt }, risk: { current: 0.82 }, risk_series: [{ observed_at: "2026-10-07T07:00:00Z", failure_probability: 0.46 }, { observed_at: "2026-10-07T08:00:00Z", failure_probability: 0.65 }, { observed_at: asset.observedAt, failure_probability: 0.82 }], features: [], operation_context: { production_plan: { planned_units: 320, plan_date: "2026-10-07" }, capacity_model: { asset_units_per_hour: 80, basis: "fixture capacity" }, event_impact: { estimated_lost_units: 160, product_variant: "가공 품목" }, limitations: ["고정 fixture의 참고값이며 실제 생산 승인 또는 확정 손실이 아닙니다."] } };
const summary = { asset_id: assetId, mode: "llm", summary: "생산 영향과 점검 기록을 함께 확인하세요.", source_refs: ["maintenance-request", "production-plan"], limitations: ["고정 fixture의 참고값이며 실제 생산 승인 또는 확정 손실이 아닙니다."], role_summaries: [{ role: "process_manager", quote: "현재 정비 요청은 생산 일정과 대조가 필요한 단계입니다. [[ref:maintenance-request]]\n요청 정지 시간 120분은 생산 계획 기준으로 비교한 참고값입니다. [[ref:production-plan]]\n승인 또는 재협의는 생산관리자가 근거를 확인한 뒤 결정합니다." }] };

// Test-only replay: real production-review component and CSS, fixed read-only responses.
const originalFetch = window.fetch.bind(window);
window.fetch = async (input) => {
  const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url, location.href);
  if (url.pathname === "/health/ready") return Response.json({ status: "ok" });
  if (!url.pathname.startsWith("/api/")) return originalFetch(input);
  if (url.pathname.endsWith("/inspection-coordinations")) return Response.json({ items: [coordination] });
  if (url.pathname.endsWith("/detail-view")) return Response.json(detail);
  if (url.pathname.endsWith(`/events/${eventId}/lineage`)) return Response.json({ event_id: eventId, work_orders: [], inspection_results: [], recommendations: [], cost_analyses: [] });
  if (url.pathname.endsWith("/agent-review-summary")) return Response.json({ summary, trace: { provider: "controlled-fixture", fallback: false, reason: null, validation_errors: [], reuse_eligibility: "EXACT_VALIDATED", current_ready: true, historical_available: false, materialization: { status: "ready", summary_key: "solutionlink-main-fixture", decision_as_of: asset.observedAt } } });
  if (url.pathname.endsWith("/agent-review-packet")) return Response.json({ project_id: projectId, asset_id: assetId, generated_at: asset.observedAt, snapshot_basis: { event_id: eventId }, source_refs: ["maintenance-request", "production-plan"], evidence_context: { selected_basis: [{ candidate_id: "maintenance-request", source_ref: "maintenance-request", fact_type: "maintenance_request", value_summary: "점검 요청 · 정지 120분", display_fields: [{ label: "정비 요청", value: "공구 체결부 점검" }, { label: "요청 정지 시간", value: "120분" }], relation_paths: [] }, { candidate_id: "production-plan", source_ref: "production-plan", fact_type: "production_plan", value_summary: "생산 계획 · 참고 산정", display_fields: [{ label: "생산 계획", value: "당일 가공 순서" }, { label: "영향 기준", value: "정지 시간 참고값" }], relation_paths: [] }] } });
  if (url.pathname.endsWith("/demo-scenario")) return Response.json({ mode: "live", options: {} });
  return Response.json({ items: [] });
};

function Preview() {
  const model = { context: { workspaceName: "공장 A · 촬영용 고정 입력", datasetVersionId: "solutionlink-fixture" }, assets: [asset], equipmentOverview: { assets: [asset] }, metrics: { estimatedDowntimeMinutes: 120 } };
  return <DisplayPreferencesProvider scope="guest"><ProductionRequestBoard canGenerateBrief={false} projectId={projectId} workspaceId={workspaceId} model={model as never} workOrders={[order] as never} workOrderError={false} currentUser={{ displayName: "화면 검토", title: "생산관리자" }} onRefresh={() => undefined} onLogout={() => undefined}/></DisplayPreferencesProvider>;
}

createRoot(document.getElementById("root")!).render(<Preview/>);
