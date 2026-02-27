import { useState, useRef, useCallback, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { GlassCard } from '../components/ui/GlassCard';
import { Button } from '../components/ui/Button';
import { detectFace, enrollFace } from '../services/api';

type EnrollmentStep = 'welcome' | 'name' | 'capture' | 'processing' | 'success';

interface CaptureGuide {
    label: string;
    emoji: string;
    instruction: string;
}

const CAPTURE_GUIDES: CaptureGuide[] = [
    { label: 'Look straight', emoji: '🙂', instruction: 'Look directly at the camera' },
    { label: 'Tilt down', emoji: '🙂', instruction: 'Lower your chin slightly' },
    { label: 'Tilt up', emoji: '🙂', instruction: 'Raise your chin slightly' },
];

export function EnrollmentView() {
    const { setView, setCurrentUser } = useApp();
    const [step, setStep] = useState<EnrollmentStep>('welcome');
    const [name, setName] = useState('');

    // Capture state
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const [captureIndex, setCaptureIndex] = useState(0);
    const [capturedImages, setCapturedImages] = useState<string[]>([]);
    const [isCapturing, setIsCapturing] = useState(false);
    const [captureStatus, setCaptureStatus] = useState<'idle' | 'detecting' | 'ok' | 'no_face'>('idle');

    // Processing / result state
    const [enrollError, setEnrollError] = useState<string | null>(null);
    const [qualityScore, setQualityScore] = useState<number | null>(null);

    // ── Webcam management ──────────────────────────────────────────────
    const startCamera = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' },
            });
            streamRef.current = stream;
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }
        } catch (err) {
            console.error('Camera access denied:', err);
            setCaptureStatus('no_face');
        }
    }, []);

    const stopCamera = useCallback(() => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach((t) => t.stop());
            streamRef.current = null;
        }
    }, []);

    // Start camera when entering capture step
    useEffect(() => {
        if (step === 'capture') {
            startCamera();
        }
        return () => {
            if (step === 'capture') stopCamera();
        };
    }, [step, startCamera, stopCamera]);

    // ── Capture a single frame ─────────────────────────────────────────
    const captureFrame = useCallback((): string | null => {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        if (!video || !canvas) return null;

        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        const ctx = canvas.getContext('2d');
        if (!ctx) return null;

        ctx.drawImage(video, 0, 0);
        // Get base64 without the data:image/jpeg;base64, prefix
        const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
        return dataUrl.split(',')[1];
    }, []);

    // ── Handle single capture + face detection ─────────────────────────
    const handleCapture = async () => {
        setIsCapturing(true);
        setCaptureStatus('detecting');

        const b64 = captureFrame();
        if (!b64) {
            setCaptureStatus('no_face');
            setIsCapturing(false);
            return;
        }

        try {
            const result = await detectFace(b64);
            if (result.face_detected) {
                setCaptureStatus('ok');
                const newImages = [...capturedImages, b64];
                setCapturedImages(newImages);

                // Brief pause to show the green check
                await new Promise((r) => setTimeout(r, 800));

                if (captureIndex < CAPTURE_GUIDES.length - 1) {
                    setCaptureIndex(captureIndex + 1);
                    setCaptureStatus('idle');
                } else {
                    // All captures done → process
                    stopCamera();
                    setStep('processing');
                    processEnrollment(newImages);
                }
            } else {
                setCaptureStatus('no_face');
            }
        } catch {
            setCaptureStatus('no_face');
        }

        setIsCapturing(false);
    };

    // ── Process enrollment ──────────────────────────────────────────────
    const processEnrollment = async (images: string[]) => {
        setEnrollError(null);
        try {
            const result = await enrollFace(name.trim(), images);
            setQualityScore(result.quality_score);
            setCurrentUser({
                id: Number(result.user_id.split('-')[0]) || Date.now(),
                name: result.name,
                created_at: new Date().toISOString(),
            });
            setStep('success');
        } catch (err) {
            setEnrollError(err instanceof Error ? err.message : 'Enrollment failed');
            // Go back to capture to retry
            setCapturedImages([]);
            setCaptureIndex(0);
            setStep('capture');
        }
    };

    const handleCancel = () => {
        stopCamera();
        setView('idle');
    };

    const currentGuide = CAPTURE_GUIDES[captureIndex];

    return (
        <div className="min-h-screen bg-black flex items-center justify-center p-8">
            <GlassCard className="w-full max-w-lg animate-fade-in">
                {/* ── Welcome Step ─────────────────────────────────── */}
                {step === 'welcome' && (
                    <div className="text-center">
                        <h1 className="text-3xl font-light text-white mb-2">
                            Welcome to Clarity+
                        </h1>
                        <p className="text-white/60 mb-8">
                            Let's create your profile for personalized wellness tracking.
                            We'll capture your face from a few angles so the mirror
                            can recognize you automatically.
                        </p>
                        <div className="flex flex-col gap-3">
                            <Button onClick={() => setStep('name')}>Get Started</Button>
                            <Button variant="secondary" onClick={handleCancel}>
                                Cancel
                            </Button>
                        </div>
                    </div>
                )}

                {/* ── Name Step ────────────────────────────────────── */}
                {step === 'name' && (
                    <div className="text-center">
                        <h2 className="text-2xl font-light text-white mb-2">
                            What's Your Name?
                        </h2>
                        <p className="text-white/40 text-sm mb-6">
                            This helps us personalize your experience.
                        </p>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && name.trim()) setStep('capture');
                            }}
                            placeholder="Enter your name"
                            className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-cyan-400 text-center text-lg mb-6"
                            autoFocus
                        />
                        <div className="flex flex-col gap-3">
                            <Button
                                onClick={() => setStep('capture')}
                                disabled={!name.trim()}
                            >
                                Next
                            </Button>
                            <Button
                                variant="secondary"
                                onClick={() => setStep('welcome')}
                            >
                                Back
                            </Button>
                        </div>
                    </div>
                )}

                {/* ── Capture Step ─────────────────────────────────── */}
                {step === 'capture' && (
                    <div className="text-center">
                        <h2 className="text-2xl font-light text-white mb-1">
                            Face Capture
                        </h2>
                        <p className="text-white/40 text-sm mb-4">
                            Step {captureIndex + 1} of {CAPTURE_GUIDES.length}
                        </p>

                        {/* Webcam preview */}
                        <div className="relative mx-auto mb-4 rounded-2xl overflow-hidden" style={{ width: 320, height: 240 }}>
                            <video
                                ref={videoRef}
                                autoPlay
                                playsInline
                                muted
                                className="w-full h-full object-cover"
                                style={{ transform: 'scaleX(-1)' }}
                            />
                            {/* Face detection overlay border */}
                            <div
                                className={`absolute inset-0 rounded-2xl border-4 transition-colors duration-300 pointer-events-none ${captureStatus === 'ok'
                                        ? 'border-green-400'
                                        : captureStatus === 'no_face'
                                            ? 'border-red-400'
                                            : captureStatus === 'detecting'
                                                ? 'border-yellow-400 animate-pulse'
                                                : 'border-white/20'
                                    }`}
                            />
                            {/* Status icon overlay */}
                            {captureStatus === 'ok' && (
                                <div className="absolute inset-0 flex items-center justify-center bg-green-400/20">
                                    <span className="text-5xl">✓</span>
                                </div>
                            )}
                        </div>

                        {/* Hidden canvas for frame capture */}
                        <canvas ref={canvasRef} className="hidden" />

                        {/* Guide prompt */}
                        <div className="mb-4">
                            <span className="text-4xl block mb-2">{currentGuide.emoji}</span>
                            <p className="text-white font-medium">{currentGuide.label}</p>
                            <p className="text-white/50 text-sm">{currentGuide.instruction}</p>
                        </div>

                        {/* Error message */}
                        {captureStatus === 'no_face' && (
                            <p className="text-red-400 text-sm mb-3">
                                No face detected. Adjust your position and try again.
                            </p>
                        )}
                        {enrollError && (
                            <p className="text-red-400 text-sm mb-3">{enrollError}</p>
                        )}

                        {/* Capture count indicator */}
                        <div className="flex justify-center gap-2 mb-4">
                            {CAPTURE_GUIDES.map((_, i) => (
                                <div
                                    key={i}
                                    className={`w-3 h-3 rounded-full transition-colors ${i < capturedImages.length
                                            ? 'bg-green-400'
                                            : i === captureIndex
                                                ? 'bg-cyan-400 animate-pulse'
                                                : 'bg-white/20'
                                        }`}
                                />
                            ))}
                        </div>

                        <div className="flex flex-col gap-3">
                            <Button onClick={handleCapture} disabled={isCapturing}>
                                {isCapturing ? 'Detecting…' : `Capture ${currentGuide.label}`}
                            </Button>
                            <Button variant="secondary" onClick={handleCancel}>
                                Cancel
                            </Button>
                        </div>
                    </div>
                )}

                {/* ── Processing Step ──────────────────────────────── */}
                {step === 'processing' && (
                    <div className="text-center py-8">
                        <div className="w-16 h-16 mx-auto mb-6 border-4 border-white/20 border-t-cyan-400 rounded-full animate-spin" />
                        <h2 className="text-2xl font-light text-white mb-2">
                            Creating your profile…
                        </h2>
                        <p className="text-white/50 text-sm">
                            Processing {capturedImages.length} face captures
                        </p>
                    </div>
                )}

                {/* ── Success Step ─────────────────────────────────── */}
                {step === 'success' && (
                    <div className="text-center">
                        <div className="text-6xl mb-4">🎉</div>
                        <h2 className="text-2xl font-light text-white mb-2">
                            Welcome, <span className="text-cyan-400 font-medium">{name}</span>!
                        </h2>
                        {qualityScore !== null && (
                            <p className="text-white/50 text-sm mb-2">
                                Face quality score:{' '}
                                <span className={qualityScore >= 0.8 ? 'text-green-400' : 'text-yellow-400'}>
                                    {(qualityScore * 100).toFixed(0)}%
                                </span>
                            </p>
                        )}
                        <p className="text-white/60 mb-8">
                            Your profile is ready. The mirror will now recognize you automatically!
                        </p>
                        <div className="flex flex-col gap-3">
                            <Button onClick={() => setView('analysis')}>
                                Start Analysis
                            </Button>
                            <Button variant="secondary" onClick={() => setView('idle')}>
                                Return to Mirror
                            </Button>
                        </div>
                    </div>
                )}

                {/* Progress dots */}
                <div className="flex justify-center gap-2 mt-8">
                    {(['welcome', 'name', 'capture', 'processing', 'success'] as const).map(
                        (s, i) => (
                            <div
                                key={s}
                                className={`w-2 h-2 rounded-full transition-colors ${step === s
                                        ? 'bg-cyan-400'
                                        : ['welcome', 'name', 'capture', 'processing', 'success'].indexOf(step) > i
                                            ? 'bg-white/60'
                                            : 'bg-white/20'
                                    }`}
                            />
                        )
                    )}
                </div>
            </GlassCard>
        </div>
    );
}
