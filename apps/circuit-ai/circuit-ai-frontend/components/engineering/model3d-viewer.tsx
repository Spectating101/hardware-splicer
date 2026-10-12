'use client';

import { useEffect, useRef, useState } from 'react';
import { Box, LoaderCircle } from 'lucide-react';

type Model3DMeta = { available?: boolean; reason?: string; model?: { sha256?: string; size_bytes?: number; generated_with?: string } };

/**
 * Orbit view of the server-generated GLB for one retained revision. It is a view of retained bytes: it carries no
 * authority and says plainly when the model is unavailable instead of drawing a stand-in.
 */
export function Model3DViewer({ projectId, revision }: { projectId: string; revision: number }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [meta, setMeta] = useState<Model3DMeta | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'unavailable' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const base = `/api/proxy/engineering/projects/${encodeURIComponent(projectId)}/revisions/${revision}/model3d`;

  useEffect(() => {
    let cancelled = false;
    setState('loading');
    setMessage('');
    fetch(base, { cache: 'no-store' })
      .then((response) => response.json())
      .then((body: Model3DMeta & { ok?: boolean; error?: string }) => {
        if (cancelled) return;
        if (body.ok === false) throw new Error(body.error || 'The 3D model could not be requested.');
        setMeta(body);
        if (!body.available) {
          setState('unavailable');
          setMessage(body.reason || 'No 3D model is available for this revision.');
        }
      })
      .catch((caught) => {
        if (cancelled) return;
        setState('error');
        setMessage(caught instanceof Error ? caught.message : 'The 3D model could not be requested.');
      });
    return () => { cancelled = true; };
  }, [base]);

  useEffect(() => {
    if (!meta?.available || !hostRef.current) return;
    const host = hostRef.current;
    let disposed = false;
    let frame = 0;
    let cleanup = () => {};

    (async () => {
      try {
        // Loaded on demand so the three.js bundle only ships to people who open the 3D tab.
        const THREE = await import('three');
        const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js');
        const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
        if (disposed) return;

        const scene = new THREE.Scene();
        scene.background = new THREE.Color('#0b0d12');
        const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 5000);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        host.appendChild(renderer.domElement);
        renderer.domElement.style.display = 'block';
        scene.add(new THREE.HemisphereLight('#ffffff', '#202633', 1.4));
        const key = new THREE.DirectionalLight('#ffffff', 2.2);
        key.position.set(40, 80, 60);
        scene.add(key);
        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;

        const resize = () => {
          const width = Math.max(host.clientWidth, 1);
          const height = Math.max(host.clientHeight, 1);
          renderer.setSize(width, height, false);
          renderer.domElement.style.width = '100%';
          renderer.domElement.style.height = '100%';
          camera.aspect = width / height;
          camera.updateProjectionMatrix();
        };
        const observer = new ResizeObserver(resize);
        observer.observe(host);
        resize();

        const response = await fetch(`${base}/glb`, { cache: 'no-store' });
        if (!response.ok) throw new Error(`The model file could not be loaded (${response.status}).`);
        const buffer = await response.arrayBuffer();
        if (disposed) return;
        const gltf = await new Promise<{ scene: InstanceType<typeof THREE.Group> }>((resolve, reject) => {
          new GLTFLoader().parse(buffer, '', (result) => resolve(result as never), reject);
        });
        if (disposed) return;
        scene.add(gltf.scene);

        const box = new THREE.Box3().setFromObject(gltf.scene);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        // KiCad exports metres, so a board is ~0.1 units across. Only guard against an empty model.
        const radius = Math.max(size.x, size.y, size.z, 1e-6);
        camera.position.copy(center).add(new THREE.Vector3(radius * 0.9, radius * 1.1, radius * 1.3));
        camera.near = radius / 100;
        camera.far = radius * 100;
        camera.updateProjectionMatrix();
        controls.target.copy(center);
        controls.update();
        setState('ready');

        const tick = () => {
          controls.update();
          renderer.render(scene, camera);
          frame = window.requestAnimationFrame(tick);
        };
        tick();

        cleanup = () => {
          window.cancelAnimationFrame(frame);
          observer.disconnect();
          controls.dispose();
          scene.traverse((object) => {
            const mesh = object as InstanceType<typeof THREE.Mesh>;
            if (mesh.geometry) mesh.geometry.dispose();
            const material = mesh.material as InstanceType<typeof THREE.Material> | InstanceType<typeof THREE.Material>[] | undefined;
            if (Array.isArray(material)) material.forEach((item) => item.dispose());
            else material?.dispose();
          });
          renderer.dispose();
          renderer.domElement.remove();
        };
        if (disposed) cleanup();
      } catch (caught) {
        if (!disposed) {
          setState('error');
          setMessage(caught instanceof Error ? caught.message : 'The 3D view could not start.');
        }
      }
    })();

    return () => {
      disposed = true;
      cleanup();
    };
  }, [base, meta]);

  return (
    <div className="relative h-full min-h-[470px] w-full bg-[#0b0d12]" data-testid="model3d">
      <div ref={hostRef} className="absolute inset-0" role="img" aria-label={`3D model of revision ${revision}. Drag to orbit, scroll to zoom.`} />
      {state === 'loading' ? <div className="absolute inset-0 flex items-center justify-center text-stone-400"><LoaderCircle className="h-5 w-5 animate-spin" aria-hidden="true" /></div> : null}
      {state === 'unavailable' || state === 'error' ? (
        <div className="absolute inset-0 flex items-center justify-center p-8">
          <div className="max-w-sm text-center">
            <Box className="mx-auto h-9 w-9 text-stone-600" aria-hidden="true" />
            <div className="mt-3 text-sm font-medium text-stone-200">{state === 'error' ? '3D view failed' : '3D model unavailable'}</div>
            <div className="mt-1 text-xs leading-5 text-stone-400">{message}</div>
          </div>
        </div>
      ) : null}
      {state === 'ready' ? (
        <div className="pointer-events-none absolute bottom-3 left-3 rounded bg-stone-950/70 px-2 py-1 text-[10px] text-stone-300">
          Drag to orbit · scroll to zoom{meta?.model?.generated_with ? ` · ${meta.model.generated_with}` : ''}
        </div>
      ) : null}
    </div>
  );
}
