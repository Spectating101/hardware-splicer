#!/usr/bin/env node
/*
 * Headless walk of the project journey on a running HS product server that serves the built UI:
 *   Projects home → New project (goal, owned parts, reference study) → Fielddeck bench → design view
 *   → Compare (scene and project revisions) → package and next action → plotter bench → drone bench.
 *
 * Usage: node scripts/verify_project_journey.cjs [base-url] [output-dir]
 *   base-url   default http://127.0.0.1:8795
 *   output-dir default review-ui/project-bench-20261120
 *
 * Server: HARDWARE_SPLICER_SERVE_UI=1 uvicorn hardware_splicer.product_api:app, with its own
 * HARDWARE_SPLICER_OUTPUT_ROOT and HARDWARE_SPLICER_STATE_DIR, and HARDWARE_SPLICER_DIGITAL_PYTHON set
 * to an interpreter with CadQuery so registered studies can run.
 *
 * Seeding goes through the same public API the UI uses and only when a project is missing:
 *   - a Fielddeck 5 study (registered case fielddeck-5) plus one requirement change, so it has two
 *     real revisions;
 *   - the saved project "drone-build", whose goal and constraints are copied from
 *     projects/drone-build/engineering_decision.json.
 * The pen plotter study is created through the reference-study route itself when none exists.
 *
 * Fails on any console error, page error, failed request (HTTP 4xx/5xx) or horizontal overflow.
 * Headless Chromium only (SwiftShader WebGL). Screenshots are JPEG, quality 88.
 */
const fs = require("node:fs");
const path = require("node:path");
const { randomUUID } = require("node:crypto");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const BASE = (process.argv[2] || "http://127.0.0.1:8795").replace(/\/$/, "");
const OUT = path.resolve(process.argv[3] || path.join(ROOT, "review-ui/project-bench-20261120"));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function api(route, options = {}) {
  const response = await fetch(`${BASE}${route}`, {
    ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  return { status: response.status, body };
}

async function studyCase(projectId) {
  const { status, body } = await api(`/v1/projects/${encodeURIComponent(projectId)}/digital`);
  return status === 200 ? { caseId: body.study?.summary?.case_id, history: body.history || [], study: body.study } : null;
}

async function findStudy(caseId, minimumRevisions = 1) {
  const { body } = await api("/v1/projects");
  for (const project of body.projects || []) {
    const study = await studyCase(project.project_id);
    if (study?.caseId === caseId && study.history.length >= minimumRevisions) return { id: project.project_id, ...study };
  }
  return null;
}

async function waitForJob(jobId) {
  for (let i = 0; i < 240; i += 1) {
    const { body } = await api(`/v1/jobs/${jobId}`);
    if (!["queued", "running"].includes(body.status)) return body;
    await sleep(2500);
  }
  throw new Error(`Job ${jobId} did not finish`);
}

async function ensureFielddeck() {
  let study = await findStudy("fielddeck-5", 2);
  if (study) return study.id;
  study = await findStudy("fielddeck-5", 1);
  let projectId = study?.id;
  if (!projectId) {
    console.log("Seeding: creating the Fielddeck 5 study (about a minute)…");
    const created = await api("/v1/digital/projects", { method: "POST", body: JSON.stringify({ case_id: "fielddeck-5" }) });
    if (created.status !== 201) throw new Error(`Fielddeck study not created: ${JSON.stringify(created.body)}`);
    projectId = created.body.project.project_id;
    study = await studyCase(projectId);
  }
  console.log("Seeding: running a Fielddeck requirement change (minimum work runtime 3.5 h)…");
  const requirements = { ...study.study.summary.requirements, minimum_work_runtime_h: 3.5 };
  const run = await api(`/v1/projects/${projectId}/digital/runs`, { method: "POST", body: JSON.stringify({
    base_revision: study.study.revision, change_request: "", requirements, request_id: randomUUID(),
  }) });
  if (run.status !== 202) throw new Error(`Fielddeck run not accepted: ${JSON.stringify(run.body)}`);
  const job = await waitForJob(run.body.job.job_id);
  if (job.status !== "succeeded") throw new Error(`Fielddeck run ${job.status}: ${JSON.stringify(job.error)}`);
  return projectId;
}

async function ensureDrone() {
  const existing = await api("/v1/projects/drone-build");
  if (existing.status === 200) return "drone-build";
  const decision = JSON.parse(fs.readFileSync(path.join(ROOT, "projects/drone-build/engineering_decision.json"), "utf8"));
  const snapshot = {
    projectId: "drone-build", projectName: "Drone build", mode: "greenfield", goal: decision.objective,
    intake: { goal: decision.objective, project_name: "Drone build" }, constraints: decision.constraints,
  };
  const saved = await api("/v1/projects/drone-build/snapshot", { method: "PUT", body: JSON.stringify({
    snapshot, expected_revision: 0,
    metadata: { client: "verify_project_journey", source: "projects/drone-build/engineering_decision.json" },
  }) });
  if (saved.status !== 200) throw new Error(`Drone project not saved: ${JSON.stringify(saved.body)}`);
  return "drone-build";
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const fielddeckId = await ensureFielddeck();
  const droneId = await ensureDrone();
  const plotterBefore = await findStudy("ender3-penplotter");

  const browser = await chromium.launch({ headless: true, args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"] });
  const problems = [];
  const shots = [];
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    page.on("console", (message) => { if (message.type() === "error") problems.push(`console: ${message.text()}`); });
    page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
    page.on("response", (response) => {
      if (response.status() >= 400) problems.push(`HTTP ${response.status()} ${response.request().method()} ${response.url()}`);
    });

    async function shot(name, { full = false } = {}) {
      await page.evaluate(() => document.fonts.ready);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (overflow > 0) problems.push(`${name}: page overflows horizontally by ${overflow}px`);
      const file = path.join(OUT, `${name}.jpg`);
      await page.screenshot({ path: file, type: "jpeg", quality: 88, fullPage: full });
      shots.push(path.relative(ROOT, file));
    }
    async function home() {
      await page.goto(BASE, { waitUntil: "networkidle" });
      await page.getByTestId("home-start-project").waitFor();
      await page.waitForFunction(() => !document.querySelector('[data-testid="home-start-project"]').disabled);
      await page.getByText(/Loading saved projects/).waitFor({ state: "hidden" });
    }
    async function openProject(projectId) {
      await home();
      await page.locator(`button[data-project-id=${JSON.stringify(projectId)}]`).click();
      await page.getByTestId("project-bench").waitFor({ timeout: 30000 });
      await page.locator("[data-design-state]:not([data-design-state=loading])").first().waitFor({ timeout: 30000 });
    }
    // New projects autosave after a short debounce; capture them once the save has landed.
    async function saved() {
      await page.locator(".job-status", { hasText: /^Saved r\d+$/ }).first().waitFor({ timeout: 30000 });
    }
    async function sceneSettled() {
      await page.waitForFunction(() => ["settled", "unavailable"].includes(
        document.querySelector("[data-scene-status]")?.dataset.sceneStatus), undefined, { timeout: 90000 });
      const status = await page.getAttribute("[data-scene-status]", "data-scene-status");
      if (status !== "settled") problems.push(`scene did not render: ${await page.locator(".fd-stage-message").innerText()}`);
      await page.waitForTimeout(1500);
    }

    // 1. Projects home.
    await home();
    await shot("01-projects-home");

    // 2. Intake: start from a goal (the wizard records the goal; no engine call).
    await page.getByTestId("home-start-project").click();
    await page.getByTestId("new-project").waitFor();
    await page.locator("#goal").fill("A4 pen plotter that reuses two salvaged NEMA17 steppers");
    await shot("02-new-project-goal");
    for (let step = 0; step < 8; step += 1) {
      const finish = page.getByRole("button", { name: "Continue to Design", exact: true });
      if (await finish.count()) { await finish.click(); break; }
      await page.getByRole("button", { name: "Continue", exact: true }).click();
      await page.waitForTimeout(400);
    }
    await page.getByTestId("project-bench").waitFor({ timeout: 30000 });
    await page.locator("[data-design-state]:not([data-design-state=loading])").first().waitFor();
    await saved();
    await page.waitForLoadState("networkidle");
    await shot("03-bench-from-goal");

    // 3. Intake: start from parts you own.
    await page.getByRole("button", { name: "Projects", exact: true }).click();
    await page.getByTestId("home-start-project").click();
    await page.getByRole("button", { name: "Start from parts you have", exact: true }).click();
    await page.getByLabel("Name").fill("Salvaged NEMA17 stepper (printer Y axis)");
    await page.getByLabel("Source").selectOption("salvaged");
    await page.getByLabel("Known facts").fill("42 mm flange; rated current not known");
    await page.getByLabel("Goal or requirements (optional)").fill("A4 pen plotter from salvaged steppers");
    await shot("04-new-project-parts");
    await page.getByRole("button", { name: "Create project from parts", exact: true }).click();
    await page.getByTestId("project-bench").waitFor({ timeout: 30000 });
    await page.locator("[data-design-state]:not([data-design-state=loading])").first().waitFor();
    await saved();
    await page.waitForLoadState("networkidle");
    await shot("05-bench-from-parts");

    // 4. Intake: start from a reference study (the pen plotter).
    await page.getByRole("button", { name: "Projects", exact: true }).click();
    await page.getByTestId("home-start-project").click();
    await page.getByRole("button", { name: "Start from a reference study", exact: true }).click();
    await page.getByText("Available designs").waitFor();
    await page.locator(".study-options label", { hasText: /pen plotter/i }).first().click();
    await shot("06-new-project-reference");
    let plotterId = plotterBefore?.id;
    if (!plotterId) {
      await page.getByRole("button", { name: "Start digital design", exact: true }).click();
      await page.getByTestId("project-bench").waitFor({ timeout: 300000 });
      plotterId = (await findStudy("ender3-penplotter"))?.id;
    }
    if (!plotterId) throw new Error("No pen plotter study exists after the reference-study route.");

    // 5. Fielddeck bench: design view, scene Compare and Face view, revision Compare, package.
    await openProject(fielddeckId);
    await sceneSettled();
    await shot("07-fielddeck-bench");
    const scene = page.getByTestId("fielddeck-scene");
    await scene.getByRole("group", { name: "Revision" }).getByRole("button", { name: "Compare", exact: true }).click();
    await page.waitForTimeout(1500);
    await scene.screenshot({ path: path.join(OUT, "08-fielddeck-scene-compare.jpg"), type: "jpeg", quality: 88 });
    shots.push(path.relative(ROOT, path.join(OUT, "08-fielddeck-scene-compare.jpg")));
    const face = scene.getByRole("button", { name: "Face view", exact: true });
    if (await face.count()) {
      await face.first().click();
      await page.waitForTimeout(2000);
      await scene.screenshot({ path: path.join(OUT, "09-fielddeck-face-view.jpg"), type: "jpeg", quality: 88 });
      shots.push(path.relative(ROOT, path.join(OUT, "09-fielddeck-face-view.jpg")));
      await scene.getByRole("button", { name: "Back to 3D", exact: true }).first().click();
    } else problems.push("Face view control is missing on the Fielddeck scene");
    await page.getByRole("button", { name: "Compare revisions", exact: true }).click();
    await page.getByTestId("revision-compare").waitFor({ timeout: 30000 });
    await page.getByTestId("revision-compare").scrollIntoViewIfNeeded();
    await shot("10-fielddeck-revision-compare");
    await page.getByTestId("bench-package").scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await shot("11-fielddeck-package-next-action");
    await page.getByRole("region", { name: "Evidence" }).scrollIntoViewIfNeeded();
    await shot("12-fielddeck-evidence");

    // 6. Plotter bench: single revision, no Compare, parts grouped by shape source.
    await openProject(plotterId);
    await sceneSettled();
    if (await page.getByTestId("fielddeck-scene").getByRole("button", { name: "Compare", exact: true }).count()) {
      problems.push("Plotter scene offers Compare with a single revision");
    }
    if (await page.getByRole("group", { name: "Change" }).count()) problems.push("Plotter scene shows a Change legend");
    await shot("13-plotter-bench");

    // 7. Drone bench: geometry unavailable, records only, no stage.
    await openProject(droneId);
    await page.locator("[data-design-state=records]").waitFor({ timeout: 30000 });
    if (await page.locator(".fd-stage, canvas").count()) problems.push("Drone bench drew a 3D stage");
    await page.getByText("cad_kernel_available", { exact: true }).first().waitFor();
    await shot("14-drone-bench-records");
    await page.getByTestId("bench-package").scrollIntoViewIfNeeded();
    await shot("15-drone-package-next-action");

    // 8. Phone width: the Fielddeck bench design tab.
    const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const mobile = await phone.newPage();
    mobile.on("console", (message) => { if (message.type() === "error") problems.push(`phone console: ${message.text()}`); });
    mobile.on("pageerror", (error) => problems.push(`phone pageerror: ${error.message}`));
    await mobile.goto(BASE, { waitUntil: "networkidle" });
    await mobile.waitForFunction(() => !document.querySelector('[data-testid="home-start-project"]')?.disabled);
    await mobile.getByText(/Loading saved projects/).waitFor({ state: "hidden" });
    await mobile.locator(`button[data-project-id=${JSON.stringify(fielddeckId)}]`).click();
    await mobile.getByTestId("project-bench").waitFor({ timeout: 30000 });
    await mobile.waitForFunction(() => ["settled", "unavailable"].includes(
      document.querySelector("[data-scene-status]")?.dataset.sceneStatus), undefined, { timeout: 90000 });
    await mobile.waitForTimeout(1500);
    const phoneOverflow = await mobile.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (phoneOverflow > 0) problems.push(`phone bench overflows horizontally by ${phoneOverflow}px`);
    await mobile.screenshot({ path: path.join(OUT, "16-phone-fielddeck-bench.jpg"), type: "jpeg", quality: 88 });
    shots.push(path.relative(ROOT, path.join(OUT, "16-phone-fielddeck-bench.jpg")));
    await phone.close();
  } finally {
    await browser.close();
  }
  console.log(shots.map((file) => `captured ${file}`).join("\n"));
  if (problems.length) {
    console.error(`Journey problems (${problems.length}):\n${problems.join("\n")}`);
    process.exitCode = 1;
  } else {
    console.log("Journey passed with no console errors, failed requests or overflow.");
  }
}

main().catch((error) => { console.error(error.stack || error.message); process.exitCode = 1; });
