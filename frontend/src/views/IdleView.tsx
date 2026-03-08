import { useState, useRef, useCallback, useEffect } from 'react';
import { Clock } from '../components/Clock';
import { useApp } from '../context/AppContext';
import { detectFace, recognizeFace } from '../services/api';

export function IdleView() {
    const {
        setView, setCurrentUser, setWebcamFrame, setGreeting,
        triggerRecognition, setTriggerRecognition,
        systemStatus,
    } = useApp();

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

    const getGreetingPrefix = () => {
        const hour = new Date().getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 17) return 'Good afternoon';
        return 'Good evening';
    };

    const handleRecognize = async () => {
        if (isRecognizing) return;
        setIsRecognizing(true);
        setShowCamera(true);
        setRecognizeStatus('Starting camera...');

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

            setRecognizeStatus('Looking for your face...');

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
                    b64 = frame;
                    break;
                }
                setRecognizeStatus(`Adjusting... (attempt ${attempt + 2}/3)`);
                await new Promise((r) => setTimeout(r, 700));
            }

            if (!b64) {
                setRecognizeStatus('No face detected');
                await new Promise((r) => setTimeout(r, 2000));
                setRecognizeStatus(null);
                stopCamera();
                setIsRecognizing(false);
                return;
            }

            setRecognizeStatus('Identifying...');
            const result = await recognizeFace(b64);
            stopCamera();

            if (result.match && result.name) {
                const greetMsg = `${getGreetingPrefix()}, ${result.name}.`;
                setGreeting(greetMsg);
                setRecognizeStatus(greetMsg);
                setWebcamFrame(b64);
                setCurrentUser({
                    id: result.user_id ?? crypto.randomUUID(),
                    name: result.name,
                    created_at: new Date().toISOString(),
                });
                await new Promise((r) => setTimeout(r, 1500));
                setView('dashboard');
            } else if (result.match_type === 'no_users') {
                setRecognizeStatus('No enrolled users');
                await new Promise((r) => setTimeout(r, 2000));
                setRecognizeStatus(null);
            } else if (result.match_type === 'no_face') {
                setRecognizeStatus('No face detected');
                await new Promise((r) => setTimeout(r, 2000));
                setRecognizeStatus(null);
            } else {
                setRecognizeStatus('Face not recognized');
                await new Promise((r) => setTimeout(r, 2000));
                setRecognizeStatus(null);
            }
        } catch (err) {
            console.error('Recognition failed:', err);
            setRecognizeStatus('Recognition unavailable');
            stopCamera();
            await new Promise((r) => setTimeout(r, 2000));
            setRecognizeStatus(null);
        }

        setIsRecognizing(false);
    };

    useEffect(() => {
        if (triggerRecognition && !isRecognizing) {
            setTriggerRecognition(false);
            handleRecognize();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [triggerRecognition, isRecognizing, setTriggerRecognition]);

    const statusDotColor = (() => {
        if (isRecognizing) return 'bg-cyan-400 animate-pulse';
        if (systemStatus === 'connected') return 'bg-white/20 animate-status-breathe';
        if (systemStatus === 'error') return 'bg-red-400/60';
        return 'bg-white/10';
    })();

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center relative select-none">

            {/* Camera overlay during recognition */}
            {showCamera && (
                <div className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center animate-fade-in">
                    <div className="relative rounded-2xl overflow-hidden mb-6" style={{ width: 320, height: 240 }}>
                        <video
                            ref={videoRef}
                            autoPlay playsInline muted
                            className="w-full h-full object-cover"
                            style={{ transform: 'scaleX(-1)' }}
                        />
                        <div className="absolute inset-0 rounded-2xl border border-cyan-400/20 pointer-events-none" />
                        <div className="absolute inset-0 rounded-2xl pointer-events-none"
                            style={{ boxShadow: 'inset 0 0 60px rgba(0,0,0,0.5)' }} />
                    </div>
                    <p className="text-white/50 text-sm tracking-wide">
                        {recognizeStatus || 'Recognizing...'}
                    </p>
                    <div className="mt-4 w-6 h-6 border-2 border-white/10 border-t-cyan-400/60 rounded-full animate-spin" />
                </div>
            )}

            {/* Clock — centered */}
            <div className="animate-fade-in-slow">
                <Clock showDate />
            </div>

            {/* Status dot — top-right corner */}
            <div className="absolute top-8 right-8 flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${statusDotColor} transition-colors duration-700`} />
            </div>

            {/* Status message */}
            {recognizeStatus && !showCamera && (
                <p className="mt-8 text-white/40 text-sm animate-fade-in tracking-wide z-20">
                    {recognizeStatus}
                </p>
            )}

            {/* Hidden elements for camera capture */}
            {!showCamera && (
                <video ref={videoRef} autoPlay playsInline muted
                    className="fixed opacity-0 pointer-events-none"
                    style={{ width: 640, height: 480, top: -9999 }}
                />
            )}
            <canvas ref={canvasRef} className="fixed opacity-0 pointer-events-none" style={{ top: -9999 }} />
        </div>
    );
}
