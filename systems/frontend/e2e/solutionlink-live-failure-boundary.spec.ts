import { expect, test, type Page } from "@playwright/test";
import { decisionDetailFixture } from "./fixtures/decision-detail.fixture";

const projectId = "manufacturing-demo-project";

async function signIn(page: Page) {
  await page.goto(`/login?returnTo=${encodeURIComponent(`/app/projects/${projectId}/operations?view=overview`)}`);
  await page.getByLabel("이메일").fill("manager@ontology.local");
  await page.getByLabel("비밀번호").fill("Manager!2026");
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await expect(page.getByRole("heading", { name: "지금 확인할 설비와 이상 건" })).toBeVisible();
}

test("actual Decision Workspace withholds actions and prose for injected stale, gapped evidence", async ({ page }) => {
  await page.route("**/api/objects/**/detail-view?*", async route => {
    const url = new URL(route.request().url());
    const assetId = decodeURIComponent(url.pathname.split("/").at(-2) ?? "CNC-S04-L04-01");
    const eventId = url.searchParams.get("event_id") ?? "RESULT#E2E";
    const datasetVersionId = url.searchParams.get("dataset_version_id") ?? "dsv-e2e";
    const detail = decisionDetailFixture(eventId, assetId, datasetVersionId);
    detail.data_status = { ...detail.data_status, is_stale: true, warnings: [...(detail.data_status?.warnings ?? []), "E2E failure injection: stale observation"] };
    detail.evidence = {
      ...detail.evidence,
      gaps: [
        { field: "maintenance_context", reason: "maintenance_context_missing_or_unresolved", owner_domain: "maintenance" },
        { field: "operation_context", reason: "operation_context_missing_or_unresolved", owner_domain: "operations" },
      ],
    };
    detail.closed_loop = {
      ...detail.closed_loop,
      work_orders: [{ work_order_id: "WO-E2E-MISSING-LINEAGE", work_type: "inspection", status: "approved", assigned_to: null, actor_display_name: null }],
      activities: [],
      available_actions: [],
    };
    await route.fulfill({ contentType: "application/json", json: detail });
  });
  await page.route("**/api/objects/**/agent-review-summary?*", async route => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        summary: null,
        trace: {
          provider: "e2e-failure-injection",
          fallback: true,
          reason: "summary_validation_failed",
          validation_errors: ["forbidden_claims:inspection_completed"],
          fallback_validation_errors: [],
          evidence_gaps: [
            { field: "maintenance_context", reason: "maintenance_context_missing_or_unresolved", owner_domain: "maintenance" },
            { field: "operation_context", reason: "operation_context_missing_or_unresolved", owner_domain: "operations" },
          ],
          reuse_eligibility: "INELIGIBLE",
          current_ready: false,
          historical_available: false,
          materialization: { status: "fallback", summary_key: "e2e-failure-injection" },
        },
      },
    });
  });

  await signIn(page);
  await page.getByRole("button", { name: /CNC-S04-L04-01/ }).first().click();
  await expect(page.getByRole("heading", { name: /CNC 가공기 1/ })).toBeVisible();
  await expect(page.getByLabel("관측 갱신 상태")).toContainText("새 관측 수집 대기");
  await expect(page.getByLabel("관측 갱신 상태")).toContainText("새 조치에 사용하지 않습니다");

  await page.getByLabel("이상 건 판단 흐름").getByRole("button", { name: /근거/ }).click();
  const briefing = page.getByLabel("LLM 응답");
  await expect(briefing.getByLabel("LLM과 근거 상태")).toContainText("필수 근거 2건 미확인");
  await expect(briefing.getByLabel("LLM과 근거 상태")).toContainText("근거 보완 후 생성");
  await expect(briefing.getByRole("status")).toContainText("표시하지 않았습니다");
  await expect(briefing.getByLabel("확인할 데이터")).toContainText("정비 이력과 작업 조건이 연결되지 않았습니다");
  await expect(briefing.locator(".natural-briefing-prose")).toHaveCount(0);

  await page.getByLabel("이상 건 판단 흐름").getByRole("button", { name: /조치/ }).click();
  const actionPanel = page.getByLabel("다음 판단");
  await expect(actionPanel.getByRole("status")).toContainText("최신 관측 정보와 담당 역할을 확인해 주세요");
  await actionPanel.getByLabel("조치 목록").locator("summary").click();
  await expect(actionPanel).toContainText("승인 이력 확인 필요");
  await expect(actionPanel).toContainText("현재 관측은 갱신이 지연되어 새 조치를 제시하지 않습니다");
  await expect(actionPanel).not.toContainText("점검 시작 대기");
  await expect(actionPanel.getByRole("button", { name: "점검 요청", exact: true })).toHaveCount(0);
});
