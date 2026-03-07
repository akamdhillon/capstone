import { useEffect, useRef, useState, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';
import { PoseLandmarker, FilesetResolver, DrawingUtils } from '@mediapipe/tasks-vision';

// ─── Posture Config (calibrated thresholds) ──────────────────────────────
const NECK_GOOD = 8.0;
const NECK_MODERATE = 12.0;
const TORSO_GOOD = 5.0;
const TORSO_MODERATE = 8.0;
const CAPTURE_DURATION = 5; // seconds
const PREP_DURATION = 5; // seconds
const RESULTS_DISPLAY_DURATION = 15; // seconds before auto-return

import { API_BASE_URL } from '../config';
const API_BASE = API_BASE_URL;

// ─── Helpers ─────────────────────────────────────────────────────────────
function calcAngle(x1: number, y1: number, x2: number, y2: number): number {
    const dx = Math.abs(x2 - x1);
    const dy = Math.abs(y2 - y1);
    if (dy < 1e-6) return 0;
    return (Math.atan(dx / dy) * 180) / Math.PI;
}

function getStatus(angle: number, good: number, mod: number): string {
    if (angle < good) return 'good';
    if (angle < mod) return 'moderate';
    return 'poor';
}

function statusColor(status: string): string {
    if (status === 'good') return '#4ade80';
    if (status === 'moderate') return '#facc15';
    return '#f87171';
}

interface PostureResult {
    score: number;
    status: string;
    message: string;
    neckAngle: number;
    torsoAngle: number;
    neckStatus: string;
    torsoStatus: string;
    recommendations: string[];
    framesAnalyzed: number;
}

// ─── Save results to backend ─────────────────────────────────────────────
async function savePostureResult(result: PostureResult) {
    try {
        await fetch(`${API_BASE}/api/posture/results`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                score: result.score,
                status: result.status,
                neck_angle: result.neckAngle,
                torso_angle: result.torsoAngle,
                neck_status: result.neckStatus,
                torso_status: result.torsoStatus,
                recommendations: result.recommendations,
                frames_analyzed: result.framesAnalyzed,
            }),
        });
    } catch (e) {
        console.error('Failed to save posture result:', e);
    }
}

// ═════════════════════════════════════════════════════════════════════════
export function PostureView() {
    const { setView } = useApp();
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const landmarkerRef = useRef<PoseLandmarker | null>(null);
    const animFrameRef = useRef<number>(0);
    const streamRef = useRef<MediaStream | null>(null);

    const [phase, setPhase] = useState<'loading' | 'ready' | 'capturing' | 'results'>('loading');
    const [timeLeft, setTimeLeft] = useState(CAPTURE_DURATION);
    const [liveNeck, setLiveNeck] = useState(0);
    const [liveTorso, setLiveTorso] = useState(0);
    const [result, setResult] = useState<PostureResult | null>(null);
    const [returnCountdown, setReturnCountdown] = useState(RESULTS_DISPLAY_DURATION);
    const [loadingMsg, setLoadingMsg] = useState('Loading posture model…');

    const neckBuf = useRef<number[]>([]);
    const torsoBuf = useRef<number[]>([]);
    const startTimeRef = useRef(0);
    const frameCountRef = useRef(0);
    const phaseRef = useRef<'loading' | 'ready' | 'capturing' | 'results'>('loading');

    // ─── Cleanup helper ──────────────────────────────────────────────
    const cleanup = useCallback(() => {
        cancelAnimationFrame(animFrameRef.current);
        streamRef.current?.getTracks().forEach(t => t.stop());
        landmarkerRef.current?.close();
    }, []);

    // ─── Go home ─────────────────────────────────────────────────────
    const goHome = useCallback(() => {
        cleanup();
        setView('idle');
    }, [cleanup, setView]);

    // ─── Finish Capture ──────────────────────────────────────────────
    const finishCapture = useCallback(() => {
        cancelAnimationFrame(animFrameRef.current);
        startTimeRef.current = 0;

        const neckArr = neckBuf.current;
        const torsoArr = torsoBuf.current;

        if (neckArr.length < 3) {
            const errResult: PostureResult = {
                score: 0, status: 'error', message: 'Not enough frames detected.',
                neckAngle: 0, torsoAngle: 0, neckStatus: 'unknown', torsoStatus: 'unknown',
                recommendations: ['Make sure your full upper body is visible.'], framesAnalyzed: neckArr.length,
            };
            setResult(errResult);
            setPhase('results');
            return;
        }

        const sorted = (arr: number[]) => [...arr].sort((a, b) => a - b);
        const median = (arr: number[]) => {
            const s = sorted(arr);
            const m = Math.floor(s.length / 2);
            return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
        };

        const neckMed = median(neckArr);
        const torsoMed = median(torsoArr);
        const neckSt = getStatus(neckMed, NECK_GOOD, NECK_MODERATE);
        const torsoSt = getStatus(torsoMed, TORSO_GOOD, TORSO_MODERATE);

        const recs: string[] = [];
        if (neckSt !== 'good') {
            recs.push('Forward head detected — practice chin tucks');
            recs.push('Check screen height (should be at eye level)');
        }
        if (torsoSt !== 'good') {
            recs.push('Slouching detected — sit or stand more upright');
            recs.push('Engage core muscles and retract shoulder blades');
        }

        let status: string, message: string, score: number;
        if (neckMed < NECK_GOOD && torsoMed < TORSO_GOOD) {
            status = 'good'; message = 'Excellent posture! Keep it up 💪';
            score = Math.min(100, 90 + Math.round((NECK_GOOD - neckMed) * 2));
        } else if (neckSt === 'poor' || torsoSt === 'poor') {
            status = 'poor'; message = 'Poor posture — needs correction';
            score = Math.max(20, 50 - Math.round(Math.max(neckMed - NECK_MODERATE, torsoMed - TORSO_MODERATE) * 2));
        } else {
            status = 'moderate'; message = 'Moderate posture — small corrections needed';
            score = Math.min(89, 60 + Math.round((NECK_MODERATE - neckMed) + (TORSO_MODERATE - torsoMed)));
        }
        score = Math.max(0, Math.min(100, score));

        const postureResult: PostureResult = {
            score, status, message,
            neckAngle: Math.round(neckMed * 10) / 10,
            torsoAngle: Math.round(torsoMed * 10) / 10,
            neckStatus: neckSt, torsoStatus: torsoSt,
            recommendations: recs, framesAnalyzed: frameCountRef.current,
        };

        setResult(postureResult);
        setPhase('results');
        savePostureResult(postureResult);
    }, []);

    // ─── Detection Loop ──────────────────────────────────────────────
    const runDetection = useCallback(() => {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        const landmarker = landmarkerRef.current;
        if (!video || !canvas || !landmarker || video.readyState < 2) {
            animFrameRef.current = requestAnimationFrame(runDetection);
            return;
        }

        const ctx = canvas.getContext('2d')!;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const poseResult = landmarker.detectForVideo(video, performance.now());
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (poseResult.landmarks?.length) {
            const drawingUtils = new DrawingUtils(ctx);
            const lm = poseResult.landmarks[0];

            drawingUtils.drawConnectors(lm, PoseLandmarker.POSE_CONNECTIONS, {
                color: 'rgba(34, 211, 238, 0.6)', lineWidth: 3,
            });
            drawingUtils.drawLandmarks(lm, { color: '#22d3ee', lineWidth: 1, radius: 4 });

            const w = canvas.width, h = canvas.height;
            const neck = calcAngle(lm[11].x * w, lm[11].y * h, lm[7].x * w, lm[7].y * h);
            const torso = calcAngle(lm[23].x * w, lm[23].y * h, lm[11].x * w, lm[11].y * h);

            setLiveNeck(Math.round(neck * 10) / 10);
            setLiveTorso(Math.round(torso * 10) / 10);

            // If capturing, collect angles
            if (phaseRef.current === 'capturing' && startTimeRef.current > 0) {
                neckBuf.current.push(neck);
                torsoBuf.current.push(torso);
                frameCountRef.current++;

                const elapsed = (Date.now() - startTimeRef.current) / 1000;
                setTimeLeft(Math.max(0, Math.ceil(CAPTURE_DURATION - elapsed)));

                if (elapsed >= CAPTURE_DURATION) {
                    finishCapture();
                    return;
                }
            }
        }

        animFrameRef.current = requestAnimationFrame(runDetection);
    }, [finishCapture]);

    // ─── Init: Load model → start camera → enter 'ready' phase ────────
    useEffect(() => {
        let cancelled = false;

        async function init() {
            setLoadingMsg('Loading posture model…');
            const vision = await FilesetResolver.forVisionTasks(
                'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
            );
            const landmarker = await PoseLandmarker.createFromOptions(vision, {
                baseOptions: {
                    modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',
                    delegate: 'GPU',
                },
                runningMode: 'VIDEO',
                numPoses: 1,
            });
            if (!cancelled) landmarkerRef.current = landmarker;

            setLoadingMsg('Starting camera…');
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' },
            });
            if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }
            streamRef.current = stream;

            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                videoRef.current.onloadeddata = () => {
                    if (cancelled) return;
                    // Enter 'ready' phase — prep timer will start
                    setPhase('ready');
                    phaseRef.current = 'ready';
                    animFrameRef.current = requestAnimationFrame(runDetection);
                };
            }
        }

        init();
        return () => { cancelled = true; cleanup(); };
    }, [runDetection, cleanup]);

    // ─── Prep Countdown & TTS ────────────────────────────────────────
    useEffect(() => {
        if (phase !== 'ready') return;

        setTimeLeft(PREP_DURATION);

        const interval = setInterval(() => {
            setTimeLeft(prev => {
                if (prev <= 1) {
                    clearInterval(interval);
                    // Start capture
                    neckBuf.current = [];
                    torsoBuf.current = [];
                    frameCountRef.current = 0;
                    startTimeRef.current = Date.now();
                    setTimeLeft(CAPTURE_DURATION);
                    setPhase('capturing');
                    phaseRef.current = 'capturing';
                    return CAPTURE_DURATION;
                }
                return prev - 1;
            });
        }, 1000);

        return () => {
            clearInterval(interval);
            window.speechSynthesis.cancel();
        };
    }, [phase]);

    // ─── Auto-return countdown after results ─────────────────────────
    useEffect(() => {
        if (phase !== 'results') return;
        setReturnCountdown(RESULTS_DISPLAY_DURATION);

        const interval = setInterval(() => {
            setReturnCountdown(prev => {
                if (prev <= 1) {
                    clearInterval(interval);
                    goHome();
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(interval);
    }, [phase, goHome]);

    // ─── Listen for WebSocket "go home" navigation ───────────────────
    useVoiceWebSocket(useCallback((data) => {
        if (data.navigate === 'idle') {
            goHome();
        }
    }, [goHome]));

    // ─── Render ──────────────────────────────────────────────────────
    const progress = phase === 'capturing' ? ((CAPTURE_DURATION - timeLeft) / CAPTURE_DURATION) * 100 : 0;

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center relative overflow-hidden">
            {/* Loading */}
            {phase === 'loading' && (
                <div className="flex flex-col items-center animate-fade-in z-10">
                    <div className="w-16 h-16 border-4 border-white/20 border-t-cyan-400 rounded-full animate-spin mb-6" />
                    <p className="text-white/60 text-lg">{loadingMsg}</p>
                </div>
            )}

            {/* Camera + Canvas */}
            <div className={`relative ${phase === 'loading' ? 'opacity-0 absolute' : ''}`}
                id="posture-camera-container"
                style={{ width: 640, maxWidth: '100vw' }}>
                <video ref={videoRef} autoPlay playsInline muted
                    className="w-full rounded-2xl" style={{ transform: 'scaleX(-1)' }} />
                <canvas ref={canvasRef}
                    className="absolute top-0 left-0 w-full h-full rounded-2xl pointer-events-none"
                    style={{ transform: 'scaleX(-1)' }} />

                {/* Get Ready Overlay */}
                {phase === 'ready' && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center rounded-2xl"
                        style={{ background: 'rgba(0,0,0,0.5)' }}>
                        <div className="w-5 h-5 rounded-full bg-cyan-400 animate-ping mb-6" />
                        <p className="text-white text-xl font-medium">Get into position…</p>
                        <p className="text-white/50 text-sm mt-2">Stand so your upper body is visible</p>
                        <div className="mt-8 text-cyan-400 font-mono text-5xl font-bold">{timeLeft}s</div>
                    </div>
                )}

                {/* Live Angle HUD */}
                {phase === 'capturing' && (
                    <div className="absolute top-4 left-4 flex flex-col gap-2">
                        <div className="glass px-3 py-2 flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full" style={{ background: statusColor(getStatus(liveNeck, NECK_GOOD, NECK_MODERATE)) }} />
                            <span className="text-white text-sm font-mono">Neck {liveNeck}°</span>
                        </div>
                        <div className="glass px-3 py-2 flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full" style={{ background: statusColor(getStatus(liveTorso, TORSO_GOOD, TORSO_MODERATE)) }} />
                            <span className="text-white text-sm font-mono">Torso {liveTorso}°</span>
                        </div>
                    </div>
                )}

                {/* Progress Bar */}
                {phase === 'capturing' && (
                    <div className="absolute bottom-0 left-0 right-0 p-4">
                        <div className="glass px-4 py-3">
                            <div className="flex justify-between items-center mb-2">
                                <span className="text-white/80 text-sm">Analyzing posture…</span>
                                <span className="text-cyan-400 font-mono text-sm">{timeLeft}s</span>
                            </div>
                            <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                                <div className="h-full rounded-full transition-all duration-300"
                                    style={{ width: `${progress}%`, background: 'linear-gradient(90deg, #22d3ee, #4ade80)' }} />
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Results Overlay */}
            {phase === 'results' && result && (
                <div className="absolute inset-0 bg-black/80 flex items-center justify-center p-8 animate-fade-in">
                    <div className="glass p-8 rounded-3xl max-w-lg w-full space-y-6">
                        {/* Score */}
                        <div className="flex flex-col items-center">
                            <div className="w-28 h-28 rounded-full flex items-center justify-center text-4xl font-bold border-4"
                                style={{ borderColor: statusColor(result.status), color: statusColor(result.status) }}>
                                {result.score}
                            </div>
                            <p className="text-white text-lg font-medium mt-3">{result.message}</p>
                            <p className="text-white/40 text-sm">{result.framesAnalyzed} frames • returning in {returnCountdown}s</p>
                        </div>

                        {/* Angles */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="glass-subtle p-4 text-center">
                                <p className="text-white/50 text-xs uppercase tracking-wider mb-1">Neck</p>
                                <p className="text-2xl font-mono" style={{ color: statusColor(result.neckStatus) }}>{result.neckAngle}°</p>
                                <p className="text-xs mt-1 uppercase" style={{ color: statusColor(result.neckStatus) }}>{result.neckStatus}</p>
                            </div>
                            <div className="glass-subtle p-4 text-center">
                                <p className="text-white/50 text-xs uppercase tracking-wider mb-1">Torso</p>
                                <p className="text-2xl font-mono" style={{ color: statusColor(result.torsoStatus) }}>{result.torsoAngle}°</p>
                                <p className="text-xs mt-1 uppercase" style={{ color: statusColor(result.torsoStatus) }}>{result.torsoStatus}</p>
                            </div>
                        </div>

                        {/* Recommendations */}
                        {result.recommendations.length > 0 && (
                            <div className="space-y-2">
                                <p className="text-white/60 text-sm font-medium">Recommendations</p>
                                {result.recommendations.map((rec, i) => (
                                    <div key={i} className="flex items-start gap-2">
                                        <span className="text-cyan-400 mt-0.5">•</span>
                                        <span className="text-white/70 text-sm">{rec}</span>
                                    </div>
                                ))}
                            </div>
                        )}

                        <button onClick={goHome} className="btn-secondary w-full">
                            ↩ Back to Mirror
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
