#!/usr/bin/env node
/*
 * Headless walk of the project journey on the one served HS app (hs-serve: API, scenes and built UI):
 *   Projects home → New project (goal, owned parts, reference study) → Fielddeck bench → design view
 *   → Compare (scene and project revisions) → package and next action → plotter bench → drone bench
 *   → URL routing (deep link, ?rev= reload, Back/Forward, not-found states).
 *
 * Usage: node scripts/verify_project_journey.cjs [base-url] [output-dir]
 *   base-url   default http://127.0.0.1:8787 (the hs-serve default)
 *   output-dir default review-ui/project-bench-20261120
 *
 * Server: build the UI (make splice-ui-build), then start the canonical app the documented way,
 *   HARDWARE_SPLICER_STATE_DIR=<fresh dir> HARDWARE_SPLICER_DIGITAL_PYTHON=<python with CadQuery> \
 *     make serve HS_SERVE_ARGS="--port 8796"        (or: hs-serve --ui --port 8796)
 * The state dir alone isolates the job database, outputs and projects. --ui refuses to start
 * without a UI build, so a passing walk also proves the UI came from this app.
 *
 * Browser: NODE_PATH=<dir with playwright> PLAYWRIGHT_BROWSERS_PATH=<browsers> node scripts/verify_project_journey.cjs
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
const BASE = (process.argv[2] || "http://127.0.0.1:8787").replace(/\/$/, "");
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
    const goalId = decodeURIComponent(new URL(page.url()).pathname.split("/").pop());

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
    await page.getByText("CAD kernel available", { exact: true }).first().waitFor();
    await shot("14-drone-bench-records");
    await page.getByTestId("bench-package").scrollIntoViewIfNeeded();
    await shot("15-drone-package-next-action");

    // 7b. Reopening is not editing: opening saved projects again must write no revision.
    const reopenIds = [droneId, goalId];
    const before = Object.fromEntries(await Promise.all(reopenIds.map(async (id) =>
      [id, (await api(`/v1/projects/${encodeURIComponent(id)}`)).body.project?.revision])));
    const writes = [];
    const onRequest = (request) => { if (request.method() !== "GET" && /\/v1\/projects\//.test(request.url())) writes.push(`${request.method()} ${request.url()}`); };
    page.on("request", onRequest);
    for (let round = 0; round < 3; round += 1) {
      for (const id of reopenIds) {
        if (round % 2) await openProject(id);
        else {
          await page.goto(`${BASE}/projects/${encodeURIComponent(id)}`, { waitUntil: "networkidle" });
          await page.getByTestId("project-bench").waitFor({ timeout: 30000 });
        }
        await page.waitForTimeout(1500);
      }
    }
    page.off("request", onRequest);
    if (writes.length) problems.push(`reopening saved projects wrote to them:\n  ${writes.join("\n  ")}`);
    for (const id of reopenIds) {
      const after = (await api(`/v1/projects/${encodeURIComponent(id)}`)).body.project?.revision;
      if (after !== before[id]) problems.push(`reopening ${id} moved its revision ${before[id]} → ${after}`);
    }

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

    // 8b. Evidence before the scene: on a warm server the evidence column must render within
    // EVIDENCE_BUDGET_MS of navigation, even while the 3D stage builds. Times come from an in-page
    // 20 ms poll, which also only runs when the main thread is free.
    const EVIDENCE_BUDGET_MS = 3000;
    for (const [label, id] of [["Fielddeck", fielddeckId], ["plotter", plotterId], ["drone", droneId]]) {
      const timed = await context.newPage();
      await timed.addInitScript(() => {
        window.__evidenceAt = null;
        const timer = setInterval(() => {
          const ev = document.querySelector("#bench-evidence");
          const link = ev?.querySelector("[data-testid=evidence-delta], .bench-link-state");
          const blockers = ev?.querySelector(".bench-blockers")?.innerText || "";
          if (link && !/Checking evidence/.test(ev.innerText) && !/Blockers\s*unknown\s*$/.test(blockers)) {
            window.__evidenceAt = performance.now(); clearInterval(timer);
          }
        }, 20);
      });
      await timed.goto(`${BASE}/projects/${encodeURIComponent(id)}`, { waitUntil: "commit" });
      await timed.waitForFunction(() => window.__evidenceAt !== null, undefined, { timeout: 60000, polling: 200 });
      const at = Math.round(await timed.evaluate(() => window.__evidenceAt));
      console.log(`evidence column on the ${label} bench rendered at ${at} ms`);
      if (at > EVIDENCE_BUDGET_MS) problems.push(`${label} evidence column took ${at} ms (budget ${EVIDENCE_BUDGET_MS} ms)`);
      await timed.close();
    }

    // 9. URL routing: deep link, reload, revision link, Back/Forward, unknown ids.
    await page.goto(`${BASE}/projects/${encodeURIComponent(fielddeckId)}`, { waitUntil: "networkidle" });
    await page.getByTestId("digital-study").waitFor({ timeout: 30000 });
    const picker = page.getByLabel("View revision");
    const latestRev = await picker.inputValue();
    const olderRev = await picker.locator("option").evaluateAll((options, latest) =>
      options.map((option) => option.value).find((value) => value !== latest), latestRev);
    await picker.selectOption(olderRev);
    await page.waitForURL(`**/projects/${encodeURIComponent(fielddeckId)}?rev=${olderRev}`);
    await page.reload({ waitUntil: "networkidle" });
    await page.getByTestId("digital-study").waitFor({ timeout: 30000 });
    if (await page.getByLabel("View revision").inputValue() !== olderRev) problems.push(`reload of ?rev=${olderRev} did not reopen that revision`);
    await shot("17-routing-revision-link");
    await page.goBack();
    await page.waitForURL(`**/projects/${encodeURIComponent(fielddeckId)}`);
    await page.waitForFunction((latest) => document.querySelector("select")?.closest("label") &&
      [...document.querySelectorAll("label")].find((label) => label.textContent.startsWith("View revision"))
        ?.querySelector("select").value === latest, latestRev, { timeout: 10000 })
      .catch(() => problems.push("Back from ?rev= did not return to the latest revision"));
    await page.getByTestId("nav-library").click();
    await page.waitForURL("**/library");
    await page.goBack();
    await page.getByTestId("digital-study").waitFor({ timeout: 30000 });
    await page.goForward();
    await page.waitForURL("**/library");
    await page.getByTestId("new-project").waitFor();

    // Unknown ids answer 404 from the API by design, so they run on a page without the failure listener.
    const lost = await context.newPage();
    lost.on("pageerror", (error) => problems.push(`not-found pageerror: ${error.message}`));
    await lost.goto(`${BASE}/projects/no-such-project-${Date.now()}`, { waitUntil: "networkidle" });
    await lost.getByRole("heading", { name: "Project not found" }).waitFor({ timeout: 15000 });
    await lost.screenshot({ path: path.join(OUT, "18-routing-project-not-found.jpg"), type: "jpeg", quality: 88 });
    shots.push(path.relative(ROOT, path.join(OUT, "18-routing-project-not-found.jpg")));
    await lost.goto(`${BASE}/no/such/page`, { waitUntil: "networkidle" });
    await lost.getByRole("heading", { name: "Page not found" }).waitFor({ timeout: 15000 });
    await lost.close();
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
