/* Usage: node scripts/capture_fielddeck_scene.cjs BASE_URL OUTPUT_DIR */
const { mkdir } = require("node:fs/promises");
const path = require("node:path");

async function assertCanvas(canvas) {
  const sample = await canvas.evaluate((element) => {
    const gl = element.getContext("webgl2");
    if (!gl || gl.isContextLost()) return { drawn: 0, colors: 0 };
    const width = gl.drawingBufferWidth;
    const height = gl.drawingBufferHeight;
    const pixels = new Uint8Array(width * height * 4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    let drawn = 0;
    const colors = new Set();
    for (let i = 0; i < pixels.length; i += 16) {
      if (pixels[i + 3] < 20) continue;
      drawn++;
      colors.add((pixels[i] >> 4) * 256 + (pixels[i + 1] >> 4) * 16 + (pixels[i + 2] >> 4));
    }
    return { drawn, colors: colors.size };
  });
  if (sample.drawn < 100 || sample.colors < 6) {
    throw new Error(`Blank Fielddeck canvas (${sample.drawn} visible samples, ${sample.colors} colors)`);
  }
}

async function main() {
  const [baseUrl, outputDir] = process.argv.slice(2);
  if (!baseUrl || !outputDir) {
    throw new Error("Usage: node scripts/capture_fielddeck_scene.cjs BASE_URL OUTPUT_DIR");
  }
  const { chromium } = require("playwright");
  await mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true, args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"] });
  const errors = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, reducedMotion: "no-preference" });
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    page.on("pageerror", (error) => errors.push(error.message));
    // Keep WebGL pixels readable in the capture harness without changing the production renderer.
    await page.addInitScript(() => {
      const getContext = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (type, options) {
        return getContext.call(this, type, type === "webgl2" ? { ...options, preserveDrawingBuffer: true } : options);
      };
    });

    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "3D scene (preview)", exact: true }).click();
    const scene = page.getByTestId("fielddeck-scene");
    const canvas = scene.locator("canvas[data-fielddeck-canvas='rendered']");
    const inspector = scene.getByRole("complementary", { name: "Selection details" });
    await scene.locator(".fd-stage").waitFor();
    await page.waitForFunction(() => ["settled", "unavailable"].includes(
      document.querySelector("[data-scene-status]")?.dataset.sceneStatus,
    ), undefined, { timeout: 45000 });
    if (await scene.getAttribute("data-scene-status") === "unavailable") {
      throw new Error(await scene.getByRole("status").innerText());
    }
    await canvas.waitFor({ state: "visible" });

    async function capture(name, settleMs = 200) {
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(settleMs);
      await assertCanvas(canvas);
      if (errors.length) throw new Error(errors.join("\n"));
      await page.screenshot({ path: path.join(outputDir, `${name}.png`), animations: "disabled" });
    }

    await capture("hero-end");
    await scene.getByRole("button", { name: "5-inch", exact: true }).click();
    await page.waitForTimeout(500);
    await scene.getByRole("button", { name: "Compare", exact: true }).click();
    await scene.locator('[data-row="5:part:tray-rear-left"]').click();
    await inspector.getByText("geometry changed", { exact: true }).waitFor();
    await capture("compare", 950);

    await scene.locator('[data-row="5:part:display"]').click();
    await inspector.getByText("vendor model", { exact: true }).waitFor();
    await capture("display-selected");

    await scene.locator('[data-row="5:link:display-ribbon"]').click();
    await inspector.getByText("pin_mapping_unknown", { exact: true }).waitFor();
    await scene.getByRole("button", { name: "Next stop", exact: true }).click();
    await capture("cable-selected", 3000);
    await page.setViewportSize({ width: 390, height: 844 });
    await capture("mobile");
    if (errors.length) throw new Error(errors.join("\n"));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
