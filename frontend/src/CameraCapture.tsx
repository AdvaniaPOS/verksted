import { useEffect, useRef, useState } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  onCapture: (file: File) => void;
};

/** Live camera capture modal. Uses MediaDevices.getUserMedia (back camera preferred). */
export default function CameraCapture({ open, onClose, onCapture }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError(null);
    let cancelled = false;
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => {});
        }
      } catch (e: any) {
        setError(e?.message ?? "Kunne ikke åpne kamera. Sjekk tillatelser.");
      }
    })();
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    };
  }, [open]);

  function snap() {
    const v = videoRef.current;
    const c = canvasRef.current;
    if (!v || !c || v.videoWidth === 0) return;
    setBusy(true);
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    const ctx = c.getContext("2d");
    if (!ctx) { setBusy(false); return; }
    ctx.drawImage(v, 0, 0, c.width, c.height);
    c.toBlob((blob) => {
      setBusy(false);
      if (!blob) return;
      const file = new File([blob], `kamera-${Date.now()}.jpg`, { type: "image/jpeg" });
      onCapture(file);
    }, "image/jpeg", 0.9);
  }

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl overflow-hidden max-w-3xl w-full">
        <div className="bg-slate-900 text-white px-4 py-2 flex items-center justify-between">
          <div className="font-medium">Ta bilde</div>
          <button onClick={onClose} className="text-slate-300 hover:text-white">✕</button>
        </div>
        <div className="bg-black relative aspect-video">
          {error ? (
            <div className="absolute inset-0 flex items-center justify-center text-rose-300 p-4 text-center">{error}</div>
          ) : (
            <video ref={videoRef} className="w-full h-full object-contain" muted playsInline />
          )}
          <canvas ref={canvasRef} className="hidden" />
        </div>
        <div className="p-4 flex gap-2 justify-center bg-slate-50">
          <button className="btn-secondary" onClick={onClose}>Avbryt</button>
          <button className="btn-primary px-8 py-3 text-base" onClick={snap} disabled={!!error || busy}>
            📸 Ta bilde
          </button>
        </div>
      </div>
    </div>
  );
}
