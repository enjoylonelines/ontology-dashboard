import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "playwright";

const baseUrl = (process.env.SOLUTIONLINK_CAPTURE_BASE_URL ?? "http://127.0.0.1:3100").replace(/\/$/, "");
const outputDir = resolve(process.env.SOLUTIONLINK_LIVE_CAPTURE_OUTPUT_DIR ?? "../../docs/evidence/2026-10-09-solutionlink-live-capture");
const email = process.env.SOLUTIONLINK_DEMO_EMAIL ?? "manager@ontology.local";
const password = process.env.SOLUTIONLINK_DEMO_PASSWORD ?? "Manager!2026";
const route = "/app/projects/manufacturing-demo-project/operations?view=overview&dashboard=workflow&role=field_operator&workspace_id=manufacturing-demo";
const run = (command, args) => {
  const result = spawnSync(command, args, { stdio: "pipe" });
  if (result.status !== 0) throw new Error(`${command} failed: ${result.stderr.toString()}`);
};

mkdirSync(outputDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
let recordedVideo;
try {
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1,
    recordVideo: { dir: resolve(outputDir, ".recordings"), size: { width: 1920, height: 1080 } },
  });
  const page = await context.newPage();
  const video = page.video();
  await page.goto(`${baseUrl}${route}`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("이메일").fill(email);
  await page.getByLabel("비밀번호").fill(password);
  await page.waitForTimeout(700);
  await page.getByRole("button", { name: "로그인" }).click();
  await page.waitForTimeout(900);
  await page.getByRole("checkbox", { name: "확인 필요만" }).check();
  await page.locator(".dw-machine.tone-critical").first().waitFor({ state: "visible" });
  await page.waitForTimeout(1600);

  await page.locator(".dw-machine.tone-critical").first().click();
  await page.getByRole("heading", { name: "위험 요약" }).waitFor({ state: "visible" });
  await page.waitForTimeout(1800);
  await page.evaluate(() => window.scrollTo({ top: 300, behavior: "smooth" }));
  await page.waitForTimeout(1100);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await page.waitForTimeout(900);
  await page.getByRole("button", { name: /근거 보기/ }).last().click();
  const briefing = page.getByLabel("LLM 응답");
  await briefing.getByText("확인할 데이터").waitFor({ state: "visible" });
  await page.waitForTimeout(1300);
  await page.getByLabel("데이터 연동 상태").evaluate(element => window.scrollTo({ top: Math.max(0, element.getBoundingClientRect().top + window.scrollY - 160), behavior: "smooth" }));
  await page.waitForTimeout(1400);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await page.waitForTimeout(900);
  await page.getByRole("button", { name: /조치 보기/ }).last().click();
  await page.getByRole("heading", { name: "조치 비교" }).waitFor({ state: "visible" });
  await page.getByLabel("조치 목록").evaluate(element => window.scrollTo({ top: Math.max(0, element.getBoundingClientRect().top + window.scrollY - 160), behavior: "smooth" }));
  await page.waitForTimeout(2200);
  await page.getByRole("button", { name: /검토 열기/ }).last().click();
  await page.getByRole("heading", { name: "검토 요청" }).waitFor({ state: "visible" });
  await page.waitForTimeout(2200);
  await context.close();
  recordedVideo = await video.path();
} finally {
  await browser.close();
}

if (!recordedVideo) throw new Error("Browser recording was not created");
const palette = resolve(outputDir, ".palette.png");
run("ffmpeg", ["-y", "-i", recordedVideo, "-vf", "fps=12,palettegen=stats_mode=diff", palette]);
run("ffmpeg", ["-y", "-i", recordedVideo, "-i", palette, "-lavfi", "fps=12,paletteuse=dither=bayer:bayer_scale=3", "-loop", "0", resolve(outputDir, "A-live-refactored-factory-flow.gif")]);
run("ffmpeg", ["-y", "-i", recordedVideo, "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", resolve(outputDir, "A-live-refactored-factory-flow.mp4")]);
writeFileSync(resolve(outputDir, "manifest.json"), JSON.stringify({
  captured_at: new Date().toISOString(), source: "local running application", route, viewport: "1920x1080",
  flow: ["로그인", "확인 필요 설비만 보기", "위험 설비 선택", "상황 확인", "데이터 연동 상태와 LLM 응답 조건", "조치 목록", "사람 검토"],
  capture_method: "Playwright browser recording with paced interaction and smooth scrolls",
  claims_not_supported: ["live provider quality", "production deployment", "real production approval", "operational performance"],
}, null, 2) + "\n");
console.log(`Live SolutionLink capture written to ${outputDir}`);
