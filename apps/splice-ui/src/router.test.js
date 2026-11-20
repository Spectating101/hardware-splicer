import { describe, expect, it } from "vitest";
import { VIEWS } from "./nav.js";
import { parseLocation, pathForRoute } from "./router.js";

const at = (url) => {
  const parsed = new URL(url, "http://hs.local");
  return parseLocation({ pathname: parsed.pathname, search: parsed.search });
};

describe("router", () => {
  it.each([
    ["/", VIEWS.home],
    ["/projects/new", VIEWS.newProject],
    ["/library", VIEWS.library],
    ["/library/", VIEWS.library],
    ["/library/sorting-workcell", VIEWS.sortcell],
    ["/library/cad-assembly", VIEWS.reference],
    ["/library/product-explorer", VIEWS.showcase],
    ["/advanced", VIEWS.advanced],
    ["/advanced/examples", VIEWS.example],
    ["/advanced/interface-lab", VIEWS.lab],
    ["/advanced/design-preview", VIEWS.preview],
  ])("maps %s to %s and back", (path, view) => {
    expect(at(path)).toEqual({ view });
    expect(pathForRoute({ view })).toBe(path.replace(/(.)\/$/, "$1"));
  });

  it("reads a project id and an optional saved revision", () => {
    expect(at("/projects/digital-41d8")).toEqual({ view: VIEWS.workspace, projectId: "digital-41d8", revision: null });
    expect(at("/projects/drone-build?rev=2")).toEqual({ view: VIEWS.workspace, projectId: "drone-build", revision: 2 });
    expect(at("/projects/a%20b")).toMatchObject({ projectId: "a b" });
    expect(pathForRoute({ view: VIEWS.workspace, projectId: "a b", revision: 3 })).toBe("/projects/a%20b?rev=3");
    expect(pathForRoute({ view: VIEWS.workspace, projectId: "x", revision: null })).toBe("/projects/x");
  });

  it("keeps a malformed revision visible instead of silently opening the latest", () => {
    for (const rev of ["0", "-1", "abc", "1.5", ""]) {
      expect(Number.isNaN(at(`/projects/x?rev=${rev}`).revision)).toBe(true);
    }
  });

  it("has no URL for a workspace whose project id is not known yet", () => {
    expect(pathForRoute({ view: VIEWS.workspace, projectId: null })).toBeNull();
  });

  it("routes scenes and reports unknown paths as not found", () => {
    expect(at("/scenes/fielddeck")).toEqual({ view: VIEWS.fielddeck, sceneId: "fielddeck" });
    expect(pathForRoute({ view: VIEWS.fielddeck, sceneId: "fielddeck" })).toBe("/scenes/fielddeck");
    expect(at("/nope")).toEqual({ view: VIEWS.notFound, path: "/nope" });
    expect(at("/projects/a/b")).toEqual({ view: VIEWS.notFound, path: "/projects/a/b" });
    expect(at("/projects/%E0%A4%A")).toMatchObject({ view: VIEWS.notFound });
  });
});
