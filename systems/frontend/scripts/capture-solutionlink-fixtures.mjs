import { spawnSync } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "playwright";

const baseUrl = (process.env.SOLUTIONLINK_CAPTURE_BASE_URL ?? "http://127.0.0.1:3100").replace(/\/$/, "");
const outputDir = resolve(process.env.SOLUTIONLINK_CAPTURE_OUTPUT_DIR ?? "../../docs/evidence/2026-10-08-solutionlink-capture");
const frameDir = resolve(outputDir, ".frames");
mkdirSync(frameDir, { recursive: true });

function toGif(input, output) {
  const result = spawnSync("ffmpeg", ["-y", "-framerate", "1", "-i", input, "-vf", "scale=1100:-1:flags=lanczos", "-loop", "0", output], { stdio: "pipe" });
  if (result.status !== 0) throw new Error(`GIF conversion failed: ${result.stderr.toString()}`);
}

const browser = await chromium.launch({ headless: true });
const captures = [
  {
    id: "A-production-manager-review",
    route: "/e2e/fixtures/solutionlink-factory-journey-preview.html",
    async captureFrames(page, directory) {
      await page.getByRole("heading", { name: "4구역" }).waitFor({ state: "visible" });
      console.log("saving A frame 00");
      await page.screenshot({ path: resolve(directory, "frame-00.png") });
      console.log("selecting A facility");
      await page.locator(".dw-machine").filter({ hasText: "4구역 · 4셀 · CNC 가공기 1" }).click();
      await page.waitForURL(/solutionlink-main-scenario-preview\.html/);
      await page.locator(".natural-briefing-status").waitFor({ state: "visible" });
      await page.waitForTimeout(350);
      console.log("saving A frame 01");
      await page.screenshot({ path: resolve(directory, "frame-01.png") });
    },
  },
  { id: "B-validation-hold", route: "/e2e/fixtures/solutionlink-validation-hold-preview.html", async captureFrames(page, directory) { await page.screenshot({ path: resolve(directory, "frame-00.png") }); } },
  { id: "C-evidence-gap", route: "/e2e/fixtures/solutionlink-evidence-gap-preview.html", async captureFrames(page, directory) { await page.screenshot({ path: resolve(directory, "frame-00.png") }); } },
];

try {
  for (const capture of captures) {
    console.log(`opening ${capture.id}`);
    const context = await browser.newContext({ viewport: { width: 1200, height: 760 } });
    const page = await context.newPage();
    await page.emulateMedia({ reducedMotion: "reduce" });
    // Vite keeps an HMR connection open, so networkidle would never settle here.
    await page.goto(`${baseUrl}${capture.route}`, { waitUntil: "domcontentloaded" });
    console.log(`loaded ${capture.id}`);
    await page.waitForTimeout(500);
    const captureFrames = resolve(frameDir, capture.id);
    mkdirSync(captureFrames, { recursive: true });
    await capture.captureFrames(page, captureFrames);
    console.log(`frames saved ${capture.id}`);
    await context.close();
    const target = resolve(outputDir, `${capture.id}.gif`);
    toGif(resolve(captureFrames, "frame-%02d.png"), target);
    rmSync(captureFrames, { recursive: true, force: true });
    console.log(`captured ${capture.id}`);
  }
} finally {
  await browser.close();
}

rmSync(frameDir, { recursive: true, force: true });
rmSync(resolve(outputDir, ".raw"), { recursive: true, force: true });
writeFileSync(resolve(outputDir, "manifest.json"), JSON.stringify({
  captured_at: new Date().toISOString(),
  fixture_only: true,
  claims_not_supported: ["live provider quality", "production deployment", "real production approval", "operational performance"],
  captures: captures.map(({ id, route }) => ({ id, route })),
}, null, 2) + "\n");
console.log(`SolutionLink fixture GIFs captured to ${outputDir}`);
