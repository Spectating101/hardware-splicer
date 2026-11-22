// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const readText = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

const FONT_IMPORTS = [
  "@fontsource/ibm-plex-sans/400.css",
  "@fontsource/ibm-plex-sans/500.css",
  "@fontsource/ibm-plex-sans/600.css",
  "@fontsource/ibm-plex-sans/700.css",
  "@fontsource/ibm-plex-mono/400.css",
  "@fontsource/ibm-plex-mono/500.css",
];

describe("self-hosted UI fonts", () => {
  const indexHtml = readText("../index.html");
  const mainJsx = readText("./main.jsx");
  const stylesCss = readText("./styles.css");

  it("removes Google Fonts hosts from index.html, src/main.jsx, and src/styles.css", () => {
    for (const content of [indexHtml, mainJsx, stylesCss]) {
      expect(content).not.toContain("fonts.googleapis.com");
      expect(content).not.toContain("fonts.gstatic.com");
    }
  });

  it("imports each self-hosted IBM Plex weight in src/main.jsx", () => {
    for (const specifier of FONT_IMPORTS) {
      const pattern = new RegExp(`^\\s*import\\s+["']${specifier.replaceAll(".", "\\.")}["'];?\\s*$`, "m");
      expect(mainJsx).toMatch(pattern);
    }
  });

  it("keeps IBM Plex Sans and IBM Plex Mono family declarations in src/styles.css", () => {
    expect(stylesCss).toContain('"IBM Plex Sans"');
    expect(stylesCss).toContain('"IBM Plex Mono"');
  });
});
