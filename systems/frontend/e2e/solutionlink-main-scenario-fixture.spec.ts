import { expect, test } from "@playwright/test";

test("replays the production-manager review without submitting a decision", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/e2e/fixtures/solutionlink-factory-journey-preview.html");

  await expect(page.getByRole("heading", { name: "1구역" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "2구역" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "3구역" })).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "4구역" })).toBeVisible();
  await page.locator(".dw-machine").filter({ hasText: "4구역 · 4셀 · CNC 가공기 1" }).click();
  await expect(page).toHaveURL(/solutionlink-main-scenario-preview\.html/);

  await expect(page.getByLabel("생산 대응 검토")).toContainText("현재 근거 기준");
  await expect(page.getByLabel("생산 대응 검토")).toContainText("승인 또는 재협의는 생산관리자가 근거를 확인한 뒤 결정합니다");
  await expect(page.getByLabel("작업 승인 검토")).toContainText("정지 시간 / 영향 품목");
  await expect(page.getByLabel("작업 승인 검토")).toContainText("120분 / 가공 품목");
  await expect(page.getByLabel("LLM 응답")).toContainText("요청 정지 시간 120분은 생산 계획 기준으로 비교한 참고값입니다");
  await expect(page.getByRole("button", { name: "작업 승인", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "재협의 요청", exact: true })).toBeDisabled();
});
