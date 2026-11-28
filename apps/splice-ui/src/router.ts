import { useCallback, useEffect, useState } from "react";
import { VIEWS } from "./nav.js";

export type StaticView =
  | "bench"
  | "home"
  | "new-project"
  | "library"
  | "sortcell"
  | "reference"
  | "showcase"
  | "advanced"
  | "example"
  | "lab"
  | "preview";

export type View = StaticView | "workspace" | "fielddeck" | "device" | "not-found";

export interface LocationLike {
  pathname?: string;
  search?: string;
}

export interface StaticRoute {
  view: StaticView;
}

export interface WorkspaceRoute {
  view: "workspace";
  projectId?: string | null;
  revision?: number | null;
}

export interface FieldDeckRoute {
  view: "fielddeck";
  sceneId?: string | null;
}

export interface DeviceRoute {
  view: "device";
  sceneId?: string | null;
}

export interface NotFoundRoute {
  view: "not-found";
  path?: string | null;
}

export type Route = StaticRoute | WorkspaceRoute | FieldDeckRoute | DeviceRoute | NotFoundRoute;

export interface NavigateOptions {
  replace?: boolean;
}

export type NavigateFn = (next: Route, options?: NavigateOptions) => void;

/**
 * History-based routes for the served SPA. The backend answers every non-API path with
 * index.html, so each of these URLs can be reloaded, linked and reached with Back/Forward.
 *
 *   /                          Workbench: the spine, HS tools and outside tools
 *   /projects                  Projects
 *   /projects/new              intake
 *   /projects/<id>[?rev=N]     project bench (optionally a saved revision)
 *   /library[/<reference>]     design library and its reference projects
 *   /advanced[/<tool>]         developer tools
 *   /scenes/<id>               a scene manifest opened full screen
 *   /devices/<id>              the device workspace for a scene: questions compose the model
 */
const STATIC: ReadonlyArray<readonly [string, StaticView]> = [
  ["/", VIEWS.bench],
  ["/projects", VIEWS.home],
  ["/projects/new", VIEWS.newProject],
  ["/library", VIEWS.library],
  ["/library/sorting-workcell", VIEWS.sortcell],
  ["/library/cad-assembly", VIEWS.reference],
  ["/library/product-explorer", VIEWS.showcase],
  ["/advanced", VIEWS.advanced],
  ["/advanced/examples", VIEWS.example],
  ["/advanced/interface-lab", VIEWS.lab],
  ["/advanced/design-preview", VIEWS.preview],
];
const PATH_OF = new Map<StaticView, string>(STATIC.map(([path, view]): [StaticView, string] => [view, path]));
const VIEW_OF = new Map<string, StaticView>(STATIC);

function decode(segment: string): string | null {
  try {
    return decodeURIComponent(segment);
  } catch {
    return null;
  }
}

function parseRevision(search: string): number | null {
  const raw = new URLSearchParams(search || "").get("rev");
  if (raw === null) return null;
  return /^[1-9]\d{0,8}$/.test(raw) ? Number(raw) : NaN;
}

/** Location → route. Unknown paths become the not-found view rather than a guess. */
export function parseLocation({ pathname = "/", search = "" }: LocationLike = {}): Route {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  if (VIEW_OF.has(path)) return { view: VIEW_OF.get(path)! };
  const project = /^\/projects\/([^/]+)$/.exec(path);
  if (project) {
    const projectId = decode(project[1]);
    if (projectId) return { view: VIEWS.workspace, projectId, revision: parseRevision(search) };
  }
  const scene = /^\/scenes\/([^/]+)$/.exec(path);
  if (scene) {
    const sceneId = decode(scene[1]);
    if (sceneId) return { view: VIEWS.fielddeck, sceneId };
  }
  const device = /^\/devices\/([^/]+)$/.exec(path);
  if (device) {
    const sceneId = decode(device[1]);
    if (sceneId) return { view: VIEWS.device, sceneId };
  }
  return { view: VIEWS.notFound, path: pathname };
}

/** Route → URL. A workspace route without a project id has no URL yet. */
export function pathForRoute(route: Route): string | null {
  if (route.view === VIEWS.workspace) {
    if (!route.projectId) return null;
    const rev = Number.isInteger(route.revision) ? `?rev=${route.revision}` : "";
    return `/projects/${encodeURIComponent(route.projectId)}${rev}`;
  }
  if (route.view === VIEWS.fielddeck) return route.sceneId ? `/scenes/${encodeURIComponent(route.sceneId)}` : null;
  if (route.view === VIEWS.device) return route.sceneId ? `/devices/${encodeURIComponent(route.sceneId)}` : null;
  if (route.view === VIEWS.notFound) return route.path || null;
  return PATH_OF.get(route.view) ?? "/";
}

function currentUrl(): string {
  return `${window.location.pathname}${window.location.search}`;
}

/**
 * Route state kept in step with window.history. navigate() pushes (or replaces) an entry;
 * Back and Forward arrive through popstate. Each entry carries an index so a screen can tell
 * whether an in-app entry sits behind it.
 */
export function useRoute(): [Route, NavigateFn] {
  const [route, setRoute] = useState(() => parseLocation(window.location));

  useEffect(() => {
    if (!Number.isInteger(window.history.state?.hsIndex)) {
      window.history.replaceState({ ...(window.history.state || {}), hsIndex: 0 }, "", currentUrl());
    }
    const onPop = () => setRoute(parseLocation(window.location));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate: NavigateFn = useCallback((next: Route, { replace = false }: NavigateOptions = {}) => {
    const url = pathForRoute(next);
    if (url !== null) {
      const index: number = window.history.state?.hsIndex ?? 0;
      if (replace || url === currentUrl()) window.history.replaceState({ hsIndex: index }, "", url);
      else window.history.pushState({ hsIndex: index + 1 }, "", url);
    }
    setRoute(next);
  }, []);

  return [route, navigate];
}

/** True when Back stays inside the app. */
export function canGoBackInApp(): boolean {
  return (window.history.state?.hsIndex ?? 0) > 0;
}
