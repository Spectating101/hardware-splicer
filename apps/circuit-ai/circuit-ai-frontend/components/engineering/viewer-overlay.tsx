'use client';

import { useEffect, useRef, useState, type RefObject } from 'react';
import { Crosshair } from 'lucide-react';

/** A location on a KiCad artifact, in millimetres in the artifact's own coordinate system. */
export type ViewerPin = {
  id: string;
  relative: string;
  x_mm: number;
  y_mm: number;
  label: string;
  tone?: 'open' | 'resolved';
};

export type ViewerBox = { min_x: number; min_y: number; max_x: number; max_y: number };

export type ViewerHighlight = {
  id: string;
  relative?: string;
  bbox: ViewerBox;
  tone: 'added' | 'removed' | 'changed';
  label: string;
};

export type PlacedPin = { relative: string; kind: string; x_mm: number; y_mm: number };

type Vec = { x: number; y: number };
type Camera = {
  zoom: number;
  center: Vec;
  viewport_size: Vec;
  rotation?: { degrees?: number } | number;
  flipped?: boolean;
  world_to_screen: (point: Vec) => Vec;
  screen_to_world: (point: Vec) => Vec;
};
type ViewerLike = { viewport?: { camera?: Camera }; canvas?: HTMLCanvasElement };

function readViewer(host: HTMLElement | null): ViewerLike | null {
  const embed = host?.querySelector('kicanvas-embed:not([data-retired])') as (HTMLElement & { shadowRoot: ShadowRoot | null }) | null;
  const app = embed?.shadowRoot?.querySelector('kc-schematic-app, kc-board-app') as (HTMLElement & { viewer?: ViewerLike }) | null;
  return app?.viewer || null;
}

function cameraSignature(camera: Camera, canvas: HTMLCanvasElement, container: HTMLElement) {
  const c = canvas.getBoundingClientRect();
  const o = container.getBoundingClientRect();
  return [camera.zoom, camera.center.x, camera.center.y, camera.viewport_size.x, camera.viewport_size.y, c.left - o.left, c.top - o.top].map((n) => Math.round(n * 1000) / 1000).join('|');
}

const toneClass = {
  added: 'border-emerald-500 bg-emerald-400/15 text-emerald-100',
  removed: 'border-red-500 bg-red-400/15 text-red-100',
  changed: 'border-amber-400 bg-amber-300/15 text-amber-100',
} as const;

/**
 * Draws review marks over a KiCanvas viewer: comment pins and diff highlights, positioned from the viewer's own
 * camera so they track pan and zoom. It reports locations only; it never identifies a board object and never
 * writes anything. Rotated or flipped views are not drawn rather than drawn wrongly.
 */
export function ViewerOverlay({
  hostRef,
  activeRelative,
  activeKind,
  pins = [],
  highlights = [],
  placing = false,
  onPlace,
  onCancelPlace,
  focusId = null,
}: {
  hostRef: RefObject<HTMLDivElement | null>;
  activeRelative: string;
  activeKind: string;
  pins?: ViewerPin[];
  highlights?: ViewerHighlight[];
  placing?: boolean;
  onPlace?: (pin: PlacedPin) => void;
  onCancelPlace?: () => void;
  /** Id of a highlight to centre the viewer on and emphasise. */
  focusId?: string | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [, setTick] = useState(0);
  const lastSignature = useRef('');
  const visiblePins = pins.filter((pin) => pin.relative === activeRelative);
  const visibleBoxes = highlights.filter((box) => !box.relative || box.relative === activeRelative);
  const active = placing || visiblePins.length > 0 || visibleBoxes.length > 0;

  useEffect(() => {
    if (!active) return;
    let frame = 0;
    const loop = () => {
      const viewer = readViewer(hostRef.current);
      const camera = viewer?.viewport?.camera;
      if (viewer?.canvas && camera && containerRef.current) {
        const signature = cameraSignature(camera, viewer.canvas, containerRef.current);
        if (signature !== lastSignature.current) {
          lastSignature.current = signature;
          setTick((value) => value + 1);
        }
      }
      frame = window.requestAnimationFrame(loop);
    };
    frame = window.requestAnimationFrame(loop);
    return () => window.cancelAnimationFrame(frame);
  }, [active, hostRef, activeRelative]);

  useEffect(() => {
    if (!focusId) return;
    const target = highlights.find((box) => box.id === focusId);
    const viewer = readViewer(hostRef.current);
    const camera = viewer?.viewport?.camera;
    if (!target || !camera) return;
    const width = Math.max(target.bbox.max_x - target.bbox.min_x, 4);
    const height = Math.max(target.bbox.max_y - target.bbox.min_y, 4);
    // Keep the change comfortably inside the view without zooming out from where the reviewer already is.
    const fit = Math.min(camera.viewport_size.x / (width * 4), camera.viewport_size.y / (height * 4), 14);
    const Vector = camera.center.constructor as new (x: number, y: number) => Vec;
    camera.center = new Vector((target.bbox.min_x + target.bbox.max_x) / 2, (target.bbox.min_y + target.bbox.max_y) / 2);
    camera.zoom = Math.max(camera.zoom, fit);
    (viewer?.viewport as { callback?: () => void } | undefined)?.callback?.();
    (viewer as { draw?: () => void } | null)?.draw?.();
    // Only when the requested focus changes, not on every new highlights array.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId]);

  useEffect(() => {
    if (!placing) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onCancelPlace?.();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [placing, onCancelPlace]);

  const viewer = readViewer(hostRef.current);
  const camera = viewer?.viewport?.camera;
  const canvas = viewer?.canvas;
  const container = containerRef.current;
  const usable = Boolean(camera && canvas && container && !camera.flipped && !(typeof camera.rotation === 'number' ? camera.rotation : camera.rotation?.degrees || 0));

  function project(x: number, y: number) {
    if (!camera || !canvas || !container) return null;
    const screen = camera.world_to_screen({ x, y });
    const c = canvas.getBoundingClientRect();
    const o = container.getBoundingClientRect();
    return { left: screen.x + (c.left - o.left), top: screen.y + (c.top - o.top) };
  }

  function handlePlace(event: React.MouseEvent<HTMLDivElement>) {
    if (!camera || !canvas || !onPlace) return;
    const c = canvas.getBoundingClientRect();
    const world = camera.screen_to_world({ x: event.clientX - c.left, y: event.clientY - c.top });
    if (!Number.isFinite(world.x) || !Number.isFinite(world.y)) return;
    onPlace({
      relative: activeRelative,
      kind: activeKind,
      x_mm: Math.round(world.x * 1000) / 1000,
      y_mm: Math.round(world.y * 1000) / 1000,
    });
  }

  return (
    <div ref={containerRef} className="pointer-events-none absolute inset-0 z-[12] overflow-hidden" data-testid="viewer-overlay">
      {usable ? visibleBoxes.map((box) => {
        const a = project(box.bbox.min_x, box.bbox.min_y);
        const b = project(box.bbox.max_x, box.bbox.max_y);
        if (!a || !b) return null;
        const left = Math.min(a.left, b.left);
        const top = Math.min(a.top, b.top);
        const width = Math.max(Math.abs(b.left - a.left), 10);
        const height = Math.max(Math.abs(b.top - a.top), 10);
        return (
          <div
            key={box.id}
            data-testid="diff-highlight"
            title={box.label}
            className={`absolute rounded-sm border-2 ${toneClass[box.tone]} ${box.id === focusId ? 'ring-4 ring-white/70' : ''}`}
            style={{ left: left - 3, top: top - 3, width: width + 6, height: height + 6 }}
          >
            {box.id === focusId ? (
              <span
                data-testid="diff-highlight-label"
                className="absolute bottom-full left-0 mb-1.5 max-w-[16rem] truncate whitespace-nowrap rounded bg-stone-900/95 px-1.5 py-0.5 text-[10px] font-medium text-white shadow"
              >
                {box.label}
              </span>
            ) : null}
          </div>
        );
      }) : null}

      {usable ? visiblePins.map((pin, index) => {
        const point = project(pin.x_mm, pin.y_mm);
        if (!point) return null;
        return (
          <div
            key={pin.id}
            data-testid="thread-pin"
            title={pin.label}
            className={`absolute flex h-6 w-6 -translate-x-1/2 -translate-y-full items-center justify-center rounded-full rounded-br-none border text-[10px] font-semibold shadow ${pin.tone === 'resolved' ? 'border-stone-400 bg-stone-300 text-stone-700' : 'border-amber-600 bg-amber-400 text-stone-950'}`}
            style={{ left: point.left, top: point.top, rotate: '0deg' }}
          >
            {index + 1}
          </div>
        );
      }) : null}

      {placing ? (
        <>
          <div
            role="button"
            tabIndex={0}
            aria-label="Click the artifact to place a comment pin"
            onClick={handlePlace}
            className="pointer-events-auto absolute inset-0 cursor-crosshair bg-amber-300/5 ring-2 ring-inset ring-amber-400/60"
            data-testid="pin-placement"
          />
          <div className="pointer-events-none absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-md bg-stone-900/90 px-3 py-1.5 text-xs text-white shadow-lg">
            <Crosshair className="h-3.5 w-3.5" aria-hidden="true" />
            Click where the comment belongs. Esc to cancel.
          </div>
        </>
      ) : null}
    </div>
  );
}
