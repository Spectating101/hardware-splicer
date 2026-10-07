'use client';

import { useEffect, useState } from 'react';

// Helpers for the vendored KiCanvas viewer, shared by every screen that draws a KiCad file.

type KiCanvasBoardViewer = { zoom_to_board?: () => void; draw?: () => void };
type KiCanvasBoardApp = HTMLElement & { viewer?: KiCanvasBoardViewer };

export function useKiCanvasScript() {
  const [ready, setReady] = useState(() => (
    typeof customElements !== 'undefined' && Boolean(customElements.get('kicanvas-embed'))
  ));
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (ready) return;
    const existing = document.querySelector('script[data-kicanvas-vnext="1"]');
    if (existing) {
      const onLoad = () => setReady(true);
      const onError = () => setFailed(true);
      existing.addEventListener('load', onLoad, { once: true });
      existing.addEventListener('error', onError, { once: true });
      return () => {
        existing.removeEventListener('load', onLoad);
        existing.removeEventListener('error', onError);
      };
    }
    const script = document.createElement('script');
    script.type = 'module';
    script.src = '/kicanvas/kicanvas.js';
    script.dataset.kicanvasVnext = '1';
    script.onload = () => setReady(true);
    script.onerror = () => setFailed(true);
    document.head.appendChild(script);
  }, [ready]);

  return { ready, failed };
}

export function focusKiCanvasBoard(embed: HTMLElement) {
  let cancelled = false;
  let attempts = 0;
  let frame = 0;

  const tryFocus = () => {
    if (cancelled) return;
    attempts += 1;
    try {
      const boardApp = embed.shadowRoot?.querySelector('kc-board-app') as KiCanvasBoardApp | null;
      const viewer = boardApp?.viewer;
      if (viewer?.zoom_to_board) {
        viewer.zoom_to_board();
        viewer.draw?.();
        embed.setAttribute('data-board-fit', 'applied');
        return;
      }
    } catch {
      // KiCanvas may have rendered kc-board-app before its viewer is initialized.
    }

    if (attempts < 180) {
      frame = window.requestAnimationFrame(tryFocus);
    } else {
      embed.setAttribute('data-board-fit', 'unavailable');
    }
  };

  frame = window.requestAnimationFrame(tryFocus);
  return () => {
    cancelled = true;
    window.cancelAnimationFrame(frame);
  };
}


// KiCanvas initialises asynchronously and adds resources to itself as it goes. An embed removed before it finishes throws
// an uncaught error from inside the library, so a replaced embed is hidden and removed only once it has loaded.
export const RETIRE_AFTER_LOAD_MS = 300;
export const RETIRE_GIVE_UP_MS = 15000;
// Switching files waits this long before mounting, so flipping faster than KiCanvas can load only loads the last one.
export const SWITCH_SETTLE_MS = 120;

export type KeptCamera = { relative: string; x: number; y: number; zoom: number };
export type LooseCamera = { zoom: number; center: { x: number; y: number; constructor: unknown } };

export function cameraOf(embed: HTMLElement) {
  const app = embed.shadowRoot?.querySelector('kc-schematic-app, kc-board-app') as (HTMLElement & { viewer?: { viewport?: { camera?: LooseCamera; callback?: () => void }; draw?: () => void } }) | null;
  return { app, viewer: app?.viewer, camera: app?.viewer?.viewport?.camera };
}

export function readCamera(embed: HTMLElement, relative: string): KeptCamera | null {
  try {
    const { camera } = cameraOf(embed);
    if (!camera || !Number.isFinite(camera.zoom) || !Number.isFinite(camera.center?.x)) return null;
    return { relative, x: camera.center.x, y: camera.center.y, zoom: camera.zoom };
  } catch {
    return null;
  }
}

/** KiCanvas fits its own view as it finishes loading; put the person's view back after that. */
export function restoreCamera(embed: HTMLElement, kept: KeptCamera) {
  const apply = () => {
    try {
      const { viewer, camera } = cameraOf(embed);
      if (!viewer || !camera) return;
      const Vector = camera.center.constructor as new (x: number, y: number) => { x: number; y: number };
      camera.center = new Vector(kept.x, kept.y);
      camera.zoom = kept.zoom;
      viewer.viewport?.callback?.();
      viewer.draw?.();
    } catch {
      // A viewer that is not ready keeps its own fit.
    }
  };
  [80, 250, 600].forEach((delay) => window.setTimeout(apply, delay));
}


export type FillMode = 'faint' | 'full';
export const FAINT_FILL_OPACITY = 0.22;

/**
 * Copper pours are drawn opaque by default, which buries the tracks, pads and labels under a flat slab of colour. Faint
 * keeps them visible as context; full shows them as KiCad would. KiCanvas reads a per-layer opacity at draw time.
 */
export function applyFillMode(embed: HTMLElement, mode: FillMode) {
  try {
    const app = embed.shadowRoot?.querySelector('kc-board-app') as (HTMLElement & { viewer?: { layers?: { in_display_order?: () => Iterable<{ name: string; opacity?: number }> }; draw?: () => void } }) | null;
    const viewer = app?.viewer;
    if (!viewer?.layers?.in_display_order) return;
    for (const layer of viewer.layers.in_display_order()) {
      if (/:(F|B|In\d+)\.Cu:Zones$/.test(layer.name)) layer.opacity = mode === 'faint' ? FAINT_FILL_OPACITY : 1;
    }
    viewer.draw?.();
  } catch {
    // A viewer that is not ready keeps its own look.
  }
}

export function applyFillModeAfterLoad(embed: HTMLElement, mode: () => FillMode) {
  // The pours are painted after the load event; apply again as they appear.
  embed.addEventListener('kicanvas:load', () => [60, 250, 700].forEach((delay) => window.setTimeout(() => applyFillMode(embed, mode()), delay)), { once: true });
}

export function retireEmbed(embed: HTMLElement) {
  embed.setAttribute('data-retired', '');
  embed.style.display = 'none';
  const remove = () => embed.remove();
  if (embed.dataset.loaded === '1') {
    window.setTimeout(remove, RETIRE_AFTER_LOAD_MS);
    return;
  }
  embed.addEventListener('kicanvas:load', () => window.setTimeout(remove, RETIRE_AFTER_LOAD_MS), { once: true });
  window.setTimeout(remove, RETIRE_GIVE_UP_MS);
}


/** Point `to` at the same place as `from`. Returns true when something changed, so a caller can keep two viewers in step. */
export function copyCamera(from: HTMLElement, to: HTMLElement) {
  try {
    const source = cameraOf(from).camera;
    const target = cameraOf(to);
    if (!source || !target.camera) return false;
    const unchanged = Math.abs(target.camera.zoom - source.zoom) < 1e-9
      && Math.abs(target.camera.center.x - source.center.x) < 1e-9
      && Math.abs(target.camera.center.y - source.center.y) < 1e-9;
    if (unchanged) return false;
    const Vector = target.camera.center.constructor as new (x: number, y: number) => { x: number; y: number };
    target.camera.center = new Vector(source.center.x, source.center.y);
    target.camera.zoom = source.zoom;
    target.viewer?.viewport?.callback?.();
    target.viewer?.draw?.();
    return true;
  } catch {
    return false;
  }
}

/**
 * Keeps one KiCanvas viewer in a host element showing `text`. A replaced viewer is retired only after it has loaded, a
 * switch waits a beat so rapid changes load only the last one, and `identity` is stamped on the viewer so a reader can tell
 * which artifact it belongs to. Returns the live viewer once it has loaded.
 */
export function useKiCanvasEmbed(
  host: HTMLElement | null,
  ready: boolean,
  text: string | null,
  identity: string,
  kind: 'schematic' | 'pcb',
  options: { controls: 'basic' | 'none'; faintFills?: boolean },
) {
  const [live, setLive] = useState<{ identity: string; embed: HTMLElement } | null>(null);
  const { controls, faintFills } = options;

  useEffect(() => {
    if (!host || !ready || !text) { setLive(null); return; }
    let embed: HTMLElement | null = null;
    let stopFit: (() => void) | undefined;
    const mount = () => {
      const created = document.createElement('kicanvas-embed');
      embed = created;
      created.dataset.artifact = identity;
      created.addEventListener('kicanvas:load', () => { created.dataset.loaded = '1'; });
      if (kind === 'pcb' && faintFills) applyFillModeAfterLoad(created, () => 'faint');
      // KiCanvas reports `load` more than once; the viewer counts as live after the first, with a short settle.
      created.addEventListener('kicanvas:load', () => window.setTimeout(() => { if (created.isConnected) setLive({ identity, embed: created }); }, 250), { once: true });
      created.setAttribute('controls', controls);
      created.setAttribute('controlslist', 'nodownload nooverlay');
      const source = document.createElement('kicanvas-source');
      source.textContent = text;
      created.appendChild(source);
      host.appendChild(created);
      if (kind === 'pcb') {
        created.setAttribute('zoom', 'objects');
        stopFit = focusKiCanvasBoard(created);
      }
    };
    const switching = Boolean(host.querySelector('kicanvas-embed'));
    const timer = window.setTimeout(mount, switching ? SWITCH_SETTLE_MS : 0);
    return () => {
      window.clearTimeout(timer);
      stopFit?.();
      setLive(null);
      if (!embed) return;
      try {
        const app = embed.shadowRoot?.querySelector('kc-schematic-app, kc-board-app') as (HTMLElement & { viewer?: { on_draw?: () => void } }) | null;
        if (app?.viewer) app.viewer.on_draw = () => undefined;
      } catch {
        // Nothing queued if the viewer never initialised.
      }
      retireEmbed(embed);
    };
  }, [host, ready, text, identity, kind, controls, faintFills]);

  return live && live.identity === identity ? live.embed : null;
}
