import { useEffect, useRef, useState, useCallback } from 'react';

const CAPTURE_COUNTDOWN = 3;

interface CapturePhaseProps {
    onCapture: (base64: string) => void;
    label?: string;
    sublabel?: string;
}

export function CapturePhase({ onCapture, label = 'Position yourself', sublabel }: CapturePhaseProps) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const [countdown, setCountdown] = useState(CAPTURE_COUNTDOWN);
    const [phase, setPhase] = useState<'ready' | 'capturing'>('ready');
    const [error, setError] = useState<string | null>(null);
    const [videoReady, setVideoReady] = useState(false);

    const captureFrame = useCallback((): string | null => {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        if (!video || !canvas || !video.videoWidth || !video.videoHeight) return null;

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) return null;

        ctx.drawImage(video, 0, 0);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
        return dataUrl.split(',')[1] ?? null;
    }, []);

    useEffect(() => {
        let cancelled = false;

        async function init() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { width: 640, height: 480, facingMode: 'user' },
                });
                if (cancelled) {
                    stream.getTracks().forEach((t) => t.stop());
                    return;
                }
                streamRef.current = stream;
                const v = videoRef.current;
                if (v) {
                    v.srcObject = stream;
                    v.onloadeddata = () => setVideoReady(true);
                    if (v.readyState >= 2) setVideoReady(true);
                }
            } catch (err) {
                setError('Camera unavailable');
            }
        }

        init();
        return () => {
            cancelled = true;
            streamRef.current?.getTracks().forEach((t) => t.stop());
            streamRef.current = null;
        };
    }, []);

    useEffect(() => {
        if (phase !== 'capturing' || error) return;

        const interval = setInterval(() => {
            setCountdown((prev) => {
                if (prev <= 1) {
                    clearInterval(interval);
                    const b64 = captureFrame();
                    streamRef.current?.getTracks().forEach((t) => t.stop());
                    streamRef.current = null;
                    if (b64) {
                        onCapture(b64);
                    } else {
                        setError('Capture failed');
                    }
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(interval);
    }, [phase, captureFrame, onCapture, error]);

    // Auto-start capture countdown once video is ready
    useEffect(() => {
        if (!videoReady || phase !== 'ready' || error) return;
        const t = setTimeout(() => {
            setPhase('capturing');
            setCountdown(CAPTURE_COUNTDOWN);
        }, 1500);
        return () => clearTimeout(t);
    }, [videoReady, phase, error]);

    if (error) {
        return (
            <div className="flex flex-col items-center animate-fade-in text-center">
                <p className="text-red-400/80 text-sm mb-6">{error}</p>
                <p className="text-white/20 text-xs">Please allow camera access and try again.</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col items-center animate-fade-in">
            <div className="relative rounded-2xl overflow-hidden mb-6" style={{ width: 480, maxWidth: '90vw' }}>
                <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    className="w-full h-auto rounded-2xl"
                    style={{ transform: 'scaleX(-1)' }}
                />
                <div
                    className="absolute inset-0 rounded-2xl pointer-events-none flex flex-col items-center justify-center"
                    style={{ background: phase === 'capturing' ? 'rgba(0,0,0,0.4)' : 'rgba(0,0,0,0.5)' }}
                >
                    {phase === 'ready' && (
                        <>
                            <div className="w-4 h-4 rounded-full bg-cyan-400/60 animate-ping mb-4" />
                            <p className="text-white/90 text-lg font-light tracking-wide">{label}</p>
                            {sublabel && <p className="text-white/40 text-xs mt-2 tracking-wide">{sublabel}</p>}
                            <p className="mt-6 text-white/40 text-xs">Capturing automatically...</p>
                        </>
                    )}
                    {phase === 'capturing' && (
                        <>
                            <p className="text-white/90 text-lg font-light tracking-wide">Capturing in</p>
                            <div className="text-cyan-400 font-mono text-5xl font-light mt-4">{countdown}</div>
                        </>
                    )}
                </div>
            </div>
            <canvas ref={canvasRef} className="fixed opacity-0 pointer-events-none" style={{ top: -9999 }} />
        </div>
    );
}
