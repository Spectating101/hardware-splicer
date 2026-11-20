import { useCallback, useEffect, useState } from "react";
import { VIEWS } from "./nav.js";

/**
 * History-based routes for the served SPA. The backend answers every non-API path with
 * index.html, so each of these URLs can be reloaded, linked and reached with Back/Forward.
 *
 *   /                          Projects
 *   /projects/new              intake
 *   /projects/<id>[?rev=N]     project bench (optionally a saved revision)
 *   /library[/<reference>]     design library and its reference projects
 *   /advanced[/<tool>]         developer tools
 *   /scenes/<id>               a scene manifest opened full screen
 */
const STATIC = [
  ["/", VIEWS.home],
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
const PATH_OF = new Map(STATIC.map(([path, view]) => [view, path]));
const VIEW_OF = new Map(STATIC);

function decode(segment) {
  try {
    return decodeURIComponent(segment);
  } catch {
    return null;
  }
}

function parseRevision(search) {
  const raw = new URLSearchParams(search || "").get("rev");
  if (raw === null) return null;
  return /^[1-9]\d{0,8}$/.test(raw) ? Number(raw) : NaN;
}

/** Location → route. Unknown paths become the not-found view rather than a guess. */
export function parseLocation({ pathname = "/", search = "" } = {}) {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  if (VIEW_OF.has(path)) return { view: VIEW_OF.get(path) };
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
  return { view: VIEWS.notFound, path: pathname };
}

/** Route → URL. A workspace route without a project id has no URL yet. */
export function pathForRoute(route) {
  if (route.view === VIEWS.workspace) {
    if (!route.projectId) return null;
    const rev = Number.isInteger(route.revision) ? `?rev=${route.revision}` : "";
    return `/projects/${encodeURIComponent(route.projectId)}${rev}`;
  }
  if (route.view === VIEWS.fielddeck) return route.sceneId ? `/scenes/${encodeURIComponent(route.sceneId)}` : null;
  if (route.view === VIEWS.notFound) return route.path || null;
  return PATH_OF.get(route.view) ?? "/";
}

function currentUrl() {
  return `${window.location.pathname}${window.location.search}`;
}

/**
 * Route state kept in step with window.history. navigate() pushes (or replaces) an entry;
 * Back and Forward arrive through popstate. Each entry carries an index so a screen can tell
 * whether an in-app entry sits behind it.
 */
export function useRoute() {
  const [route, setRoute] = useState(() => parseLocation(window.location));

  useEffect(() => {
    if (!Number.isInteger(window.history.state?.hsIndex)) {
      window.history.replaceState({ ...(window.history.state || {}), hsIndex: 0 }, "", currentUrl());
    }
    const onPop = () => setRoute(parseLocation(window.location));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((next, { replace = false } = {}) => {
    const url = pathForRoute(next);
    if (url !== null) {
      const index = window.history.state?.hsIndex ?? 0;
      if (replace || url === currentUrl()) window.history.replaceState({ hsIndex: index }, "", url);
      else window.history.pushState({ hsIndex: index + 1 }, "", url);
    }
    setRoute(next);
  }, []);

  return [route, navigate];
}

/** True when Back stays inside the app. */
export function canGoBackInApp() {
  return (window.history.state?.hsIndex ?? 0) > 0;
}
