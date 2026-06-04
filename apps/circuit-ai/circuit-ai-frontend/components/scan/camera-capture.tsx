"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, RefreshCw, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  onCapture(file: File): void;
  onClose(): void;
}

type Facing = "environment" | "user";

export function CameraCapture({ onCapture, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [facing, setFacing] = useState<Facing>("environment");
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => {
    let cancelled = false;
    setReady(false);
    setError(null);

    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("Your browser doesn't expose a camera API. Try the file picker, or open this page over HTTPS.");
      return;
    }

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: facing }, audio: false })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        const v = videoRef.current;
        if (v) {
          v.srcObject = stream;
          v.onloadedmetadata = () => {
            v.play().then(() => setReady(true)).catch(() => setReady(true));
          };
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : String(err);
        setError(`Couldn't access the camera (${msg}). Permissions may be blocked, or no camera is attached.`);
      });

    return () => {
      cancelled = true;
      stopStream();
    };
  }, [facing, stopStream]);

  const shoot = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !ready) return;
    const w = video.videoWidth;
    const h = video.videoHeight;
    if (!w || !h) return;
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, w, h);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const file = new File([blob], `scan-${Date.now()}.jpg`, { type: "image/jpeg" });
      stopStream();
      onCapture(file);
    }, "image/jpeg", 0.92);
  }, [ready, onCapture, stopStream]);

  const flip = () => setFacing((f) => (f === "environment" ? "user" : "environment"));

  return (
    <div className="fixed inset-0 z-[120] flex flex-col bg-black/95 backdrop-blur">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <Camera className="h-4 w-4 text-cyan-300" /> Live camera
        </div>
        <button
          onClick={() => { stopStream(); onClose(); }}
          className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200 hover:bg-white/10"
        >
          <X className="h-3.5 w-3.5" /> Close
        </button>
      </div>

      <div className="relative flex-1 overflow-hidden">
        {error ? (
          <div className="absolute inset-0 flex items-center justify-center p-6 text-center">
            <div className="max-w-md rounded-2xl border border-rose-400/40 bg-rose-500/10 p-5 text-sm text-rose-100">
              {error}
            </div>
          </div>
        ) : (
          <>
            <video
              ref={videoRef}
              playsInline
              muted
              className="h-full w-full object-contain"
              style={{ transform: facing === "user" ? "scaleX(-1)" : undefined }}
            />
            <div className="pointer-events-none absolute inset-0">
              <CornerGuides />
            </div>
            {!ready && (
              <div className="absolute inset-0 flex items-center justify-center text-xs text-slate-400">
                Starting camera…
              </div>
            )}
          </>
        )}
      </div>

      <div className="flex items-center justify-center gap-4 border-t border-white/10 bg-black/70 px-4 py-4">
        <Button
          onClick={flip}
          size="sm"
          variant="outline"
          className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10"
        >
          <RefreshCw className="mr-2 h-4 w-4" /> Flip
        </Button>
        <button
          onClick={shoot}
          disabled={!ready || !!error}
          aria-label="Take photo"
          className="relative inline-flex h-16 w-16 items-center justify-center rounded-full border-2 border-white/80 bg-white/10 hover:bg-white/20 disabled:opacity-40"
        >
          <span className="block h-12 w-12 rounded-full bg-white" />
        </button>
        <div className="w-[92px]" />
      </div>

      <canvas ref={canvasRef} hidden />
    </div>
  );
}

function CornerGuides() {
  const corner = "absolute h-6 w-6 border-cyan-300/70";
  return (
    <>
      <span className={`${corner} left-6 top-6 border-l-2 border-t-2`} />
      <span className={`${corner} right-6 top-6 border-r-2 border-t-2`} />
      <span className={`${corner} bottom-6 left-6 border-b-2 border-l-2`} />
      <span className={`${corner} bottom-6 right-6 border-b-2 border-r-2`} />
    </>
  );
}
