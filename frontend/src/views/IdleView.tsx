import { useState, useRef, useCallback } from 'react';
import { Clock } from '../components/Clock';
import { useApp } from '../context/AppContext';
import { detectFace, recognizeFace } from '../services/api';

export function IdleView() {
    const { setView, setCurrentUser, setWebcamFrame } = useApp();
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const streamRef = useRef<MediaStream | null>(null);

    const [isRecognizing, setIsRecognizing] = useState(false);
    const [showCamera, setShowCamera] = useState(false);
    const [recognizeStatus, setRecognizeStatus] = useState<string | null>(null);

    const stopCamera = useCallback(() => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach((t) => t.stop());
            streamRef.current = null;
        }
        setShowCamera(false);
    }, []);

    const captureFrame = useCallback((): string | null => {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        if (!video || !canvas) return null;
        if (!video.videoWidth || !video.videoHeight) return null;

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) return null;

        ctx.drawImage(video, 0, 0);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
        return dataUrl.split(',')[1];
    }, []);

    const handleRecognize = async () => {
        setIsRecognizing(true);
        setShowCamera(true);
        setRecognizeStatus('Starting camera…');

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' },
            });
            streamRef.current = stream;
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }

            await new Promise<void>((resolve) => {
                const v = videoRef.current;
                if (!v) return resolve();
                if (v.readyState >= 2) return resolve();
                v.onloadeddata = () => resolve();
            });
            await new Promise((r) => setTimeout(r, 800));

            setRecognizeStatus('Looking for your face…');

            // Try up to 3 frames to find a face before sending for recognition
            let b64: string | null = null;
            for (let attempt = 0; attempt < 3; attempt++) {
                const frame = captureFrame();
                if (!frame) {
                    await new Promise((r) => setTimeout(r, 500));
                    continue;
                }
                try {
                    const detection = await detectFace(frame);
                    if (detection.face_detected) {
                        b64 = frame;
                        break;
                    }
                } catch {
                    // detection service might be down, still try recognition
                    b64 = frame;
                    break;
                }
                setRecognizeStatus(`Adjusting… (attempt ${attempt + 2}/3)`);
                await new Promise((r) => setTimeout(r, 700));
            }

            if (!b64) {
                setRecognizeStatus('No face detected. Position your face in the frame.');
                stopCamera();
                setIsRecognizing(false);
                return;
            }

            setRecognizeStatus('Identifying…');
            const result = await recognizeFace(b64);
            stopCamera();

            if (result.match && result.name) {
                setRecognizeStatus(`Welcome back, ${result.name}!`);
                setWebcamFrame(b64);
                setCurrentUser({
                    id: Date.now(),
                    name: result.name,
                    created_at: new Date().toISOString(),
                });
                await new Promise((r) => setTimeout(r, 1200));
                setView('analysis');
            } else if (result.match_type === 'no_users') {
                setRecognizeStatus('No enrolled users. Please enroll first.');
            } else if (result.match_type === 'no_face') {
                setRecognizeStatus('No face detected. Try again.');
            } else {
                setRecognizeStatus(
                    result.confidence > 0
                        ? `Not recognized (${(result.confidence * 100).toFixed(0)}% match). Try again or enroll.`
                        : 'Face not recognized. Try again or enroll.'
                );
            }
        } catch (err) {
            console.error('Recognition failed:', err);
            setRecognizeStatus('Recognition failed. Check that services are running.');
            stopCamera();
        }

        setIsRecognizing(false);
    };

    const handleCancel = () => {
        stopCamera();
        setIsRecognizing(false);
        setRecognizeStatus(null);
    };

    const handleDismissStatus = () => setRecognizeStatus(null);

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center relative">
            {/* Clock */}
            <Clock showDate className="mb-16" />

            {/* Camera preview overlay during recognition */}
            {showCamera && (
                <div className="fixed inset-0 z-50 bg-black/80 flex flex-col items-center justify-center animate-fade-in">
                    <div className="relative rounded-2xl overflow-hidden mb-6" style={{ width: 320, height: 240 }}>
                        <video
                            ref={videoRef}
                            autoPlay
                            playsInline
                            muted
                            className="w-full h-full object-cover"
                            style={{ transform: 'scaleX(-1)' }}
                        />
                        <div className="absolute inset-0 rounded-2xl border-4 border-cyan-400/40 animate-pulse pointer-events-none" />
                    </div>
                    <p className="text-white/70 text-sm mb-2">
                        {recognizeStatus || 'Recognizing…'}
                    </p>
                    <div className="w-5 h-5 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin mb-4" />
                    <button
                        onClick={handleCancel}
                        className="text-white/40 hover:text-white/70 text-sm transition-colors"
                    >
                        Cancel
                    </button>
                </div>
            )}

            {/* Recognize Me button */}
            <button
                onClick={handleRecognize}
                disabled={isRecognizing}
                className={`
                    px-8 py-4 rounded-2xl text-lg font-medium transition-all duration-300
                    ${isRecognizing
                        ? 'bg-cyan-400/10 text-cyan-400/60 cursor-wait border border-cyan-400/30'
                        : 'bg-white/5 hover:bg-cyan-400/10 text-white/70 hover:text-cyan-400 border border-white/10 hover:border-cyan-400/40 hover:shadow-[0_0_30px_rgba(34,211,238,0.15)]'
                    }
                `}
            >
                {isRecognizing ? (
                    <span className="flex items-center gap-3">
                        <span className="w-5 h-5 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" />
                        Recognizing…
                    </span>
                ) : (
                    <span className="flex items-center gap-3">
                        <span className="text-2xl">👤</span>
                        Recognize Me
                    </span>
                )}
            </button>

            {/* Status message (when not recognizing) */}
            {!isRecognizing && recognizeStatus && (
                <button
                    onClick={handleDismissStatus}
                    className="mt-4 text-white/50 text-sm animate-fade-in hover:text-white/70 transition-colors"
                >
                    {recognizeStatus} <span className="text-white/30 ml-1">✕</span>
                </button>
            )}

            {/* Off-screen canvas + fallback video for frame capture */}
            {!showCamera && (
                <video ref={videoRef} autoPlay playsInline muted
                    className="fixed opacity-0 pointer-events-none"
                    style={{ width: 640, height: 480, top: -9999 }}
                />
            )}
            <canvas ref={canvasRef} className="fixed opacity-0 pointer-events-none" style={{ top: -9999 }} />

            {/* Subtle prompt */}
            <p className="absolute bottom-20 text-white/20 text-sm animate-pulse-subtle tracking-wide">
                Tap above to identify yourself
            </p>

            {/* Enrollment link */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    setView('enrollment');
                }}
                className="absolute bottom-8 text-white/20 hover:text-white/40 text-sm transition-colors"
            >
                New user? Tap to enroll
            </button>
        </div>
    );
}
