#!/usr/bin/env node
/*
 * Headless capture of the bench after a requirement change (sibling of verify_project_journey.cjs).
 *
 * Run scripts/demo_revision_staleness.py against the same served app first; it leaves a
 * Fielddeck 5 study whose latest revision changed the runtime target. This walk opens that
 * study's bench and requires, from backend data only:
 *   - the changed requirement and a "stale · from revision N" row for the affected check;
 *   - the rerun failure kept under "Failing in revision N+1";
 *   - the before/after STUDY.zip pair with hashes;
 *   - no "ready" wording and no physical authorisation.
 *
 * Usage: node scripts/verify_revision_staleness.cjs [base-url] [output-dir] [project-id]
 *   base-url   default http://127.0.0.1:8787; output-dir default review-ui/project-bench-20261120
 * Browser: NODE_PATH=<dir with playwright> PLAYWRIGHT_BROWSERS_PATH=<browsers> node scripts/verify_revision_staleness.cjs
 * Fails on any console error, page error, failed request (HTTP 4xx/5xx) or horizontal overflow.
 * Screenshots are JPEG, quality 88, named staleness-*.jpg.
 */
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const BASE = (process.argv[2] || "http://127.0.0.1:8787").replace(/\/$/, "");
const OUT = path.resolve(process.argv[3] || path.join(ROOT, "review-ui/project-bench-20261120"));

async function api(route, options = {}) {
  const response = await fetch(`${BASE}${route}`, { ...options, headers: { "Content-Type": "application/json" } });
  return { status: response.status, body: await response.json().catch(() => ({})) };
}

// The newest Fielddeck 5 study whose latest revision has a backend study-check delta.
async function findChangedStudy() {
  if (process.argv[4]) return process.argv[4];
  const { body } = await api("/v1/projects");
  for (const project of body.projects || []) {
    const { status, body: state } = await api(`/v1/projects/${encodeURIComponent(project.project_id)}/digital`);
    if (status !== 200 || state.study?.summary?.case_id !== "fielddeck-5" || state.study.revision < 2) continue;
    const delta = await api(`/v1/projects/${encodeURIComponent(project.project_id)}/engineering/assurance/evidence-delta`, {
      method: "POST", body: JSON.stringify({ base_revision: state.study.revision - 1, candidate_revision: state.study.revision }),
    });
    if (delta.body.evidence_delta?.study_checks?.stale_outputs?.length) return project.project_id;
  }
  throw new Error("No Fielddeck 5 study with stale checks; run scripts/demo_revision_staleness.py first.");
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const projectId = await findChangedStudy();
  const { body: state } = await api(`/v1/projects/${encodeURIComponent(projectId)}/digital`);
  const latest = state.study.revision;
  const delta = (await api(`/v1/projects/${encodeURIComponent(projectId)}/engineering/assurance/evidence-delta`, {
    method: "POST", body: JSON.stringify({ base_revision: latest - 1, candidate_revision: latest }),
  })).body.evidence_delta.study_checks;
  const staleIds = delta.stale_outputs.map((row) => row.metadata.summary);
  const failingIds = delta.failing_outputs.map((row) => row.summary);

  const browser = await chromium.launch({ headless: true, args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"] });
  const problems = [];
  const shots = [];
  const watch = (page, label) => {
    page.on("console", (message) => { if (message.type() === "error") problems.push(`${label} console: ${message.text()}`); });
    page.on("pageerror", (error) => problems.push(`${label} pageerror: ${error.message}`));
    page.on("response", (response) => {
      if (response.status() >= 400) problems.push(`${label} HTTP ${response.status()} ${response.request().method()} ${response.url()}`);
    });
  };
  async function shot(page, name, locator) {
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (overflow > 0) problems.push(`${name}: page overflows horizontally by ${overflow}px`);
    const file = path.join(OUT, `${name}.jpg`);
    await (locator || page).screenshot({ path: file, type: "jpeg", quality: 88 });
    shots.push(path.relative(ROOT, file));
  }
  async function open(page) {
    await page.goto(BASE, { waitUntil: "networkidle" });
    await page.waitForFunction(() => !document.querySelector('[data-testid="home-start-project"]')?.disabled);
    await page.getByText(/Loading saved projects/).waitFor({ state: "hidden" });
    await page.locator(`button[data-project-id=${JSON.stringify(projectId)}]`).click();
    await page.getByTestId("project-bench").waitFor({ timeout: 30000 });
  }
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    watch(page, "desktop");
    await open(page);
    const evidence = page.getByTestId("evidence-delta");
    await evidence.waitFor({ timeout: 60000 });
    const text = await evidence.innerText();
    for (const id of staleIds) {
      if (!new RegExp(`stale · from revision ${latest - 1}\\s*${id}`).test(text)) problems.push(`no stale row for ${id}`);
    }
    for (const id of failingIds) {
      if (!new RegExp(`failed · revision ${latest}\\s*${id}`).test(text)) problems.push(`no failing row for ${id}`);
    }
    if (!/Package before and after/.test(text)) problems.push("no package pair");
    for (const side of ["before", "after"]) {
      const sha = delta.packages[side]?.sha256;
      if (!sha || !text.includes(sha.slice(0, 16))) problems.push(`package ${side} hash not shown`);
    }
    const bench = await page.getByTestId("project-bench").innerText();
    if (/\bready\b/i.test(bench)) problems.push("the bench shows ready wording");
    await page.waitForTimeout(800);
    await evidence.scrollIntoViewIfNeeded();
    await shot(page, "staleness-01-evidence-delta", evidence);
    await page.getByRole("region", { name: "Evidence" }).scrollIntoViewIfNeeded();
    await shot(page, "staleness-02-bench-evidence");
    await page.getByTestId("bench-package").scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    await shot(page, "staleness-03-package-next-action");

    const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const mobile = await phone.newPage();
    watch(mobile, "phone");
    await open(mobile);
    await mobile.getByRole("tab", { name: "Evidence" }).click();
    const phoneEvidence = mobile.getByTestId("evidence-delta");
    await phoneEvidence.waitFor({ timeout: 60000 });
    await phoneEvidence.scrollIntoViewIfNeeded();
    await mobile.waitForTimeout(500);
    await shot(mobile, "staleness-04-phone-evidence");
    await phone.close();
  } finally {
    await browser.close();
  }
  console.log(`project ${projectId} revision ${latest}: stale ${staleIds.join(", ")}; failing ${failingIds.join(", ")}`);
  console.log(shots.map((file) => `captured ${file}`).join("\n"));
  if (problems.length) {
    console.error(`Staleness capture problems (${problems.length}):\n${problems.join("\n")}`);
    process.exitCode = 1;
  } else {
    console.log("Staleness capture passed with no console errors, failed requests or overflow.");
  }
}

main().catch((error) => { console.error(error.stack || error.message); process.exitCode = 1; });
