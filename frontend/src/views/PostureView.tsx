import { useEffect, useRef, useState, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';
import { PoseLandmarker, FilesetResolver, DrawingUtils } from '@mediapipe/tasks-vision';
import { API_BASE_URL } from '../config';

const NECK_GOOD = 8.0;
const NECK_MODERATE = 12.0;
const TORSO_GOOD = 5.0;
const TORSO_MODERATE = 8.0;
const CAPTURE_DURATION = 5;
const PREP_DURATION = 5;
const RESULTS_DISPLAY_DURATION = 15;

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

async function savePostureResult(result: PostureResult, userId?: string | null) {
    try {
        await fetch(`${API_BASE_URL}/api/posture/results`, {
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
                user_id: userId ?? null,
            }),
        });
    } catch (e) {
        console.error('Failed to save posture result:', e);
    }
}

export function PostureView() {
    const { setView, currentUser } = useApp();
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
    const [loadingMsg, setLoadingMsg] = useState('Loading posture model...');

    const neckBuf = useRef<number[]>([]);
    const torsoBuf = useRef<number[]>([]);
    const startTimeRef = useRef(0);
    const frameCountRef = useRef(0);
    const phaseRef = useRef<'loading' | 'ready' | 'capturing' | 'results'>('loading');

    const cleanup = useCallback(() => {
        cancelAnimationFrame(animFrameRef.current);
        streamRef.current?.getTracks().forEach(t => t.stop());
        landmarkerRef.current?.close();
    }, []);

    const goHome = useCallback(() => {
        cleanup();
        setView(currentUser ? 'dashboard' : 'idle');
    }, [cleanup, setView, currentUser]);

    const finishCapture = useCallback(() => {
        cancelAnimationFrame(animFrameRef.current);
        startTimeRef.current = 0;

        const neckArr = neckBuf.current;
        const torsoArr = torsoBuf.current;

        if (neckArr.length < 3) {
            setResult({
                score: 0, status: 'error', message: 'Not enough frames detected.',
                neckAngle: 0, torsoAngle: 0, neckStatus: 'unknown', torsoStatus: 'unknown',
                recommendations: ['Make sure your full upper body is visible.'], framesAnalyzed: neckArr.length,
            });
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
            recs.push('Forward head detected \u2014 practice chin tucks');
            recs.push('Check screen height (should be at eye level)');
        }
        if (torsoSt !== 'good') {
            recs.push('Slouching detected \u2014 sit or stand more upright');
            recs.push('Engage core muscles and retract shoulder blades');
        }

        let status: string, message: string, score: number;
        if (neckMed < NECK_GOOD && torsoMed < TORSO_GOOD) {
            status = 'good'; message = 'Excellent posture! Keep it up.';
            score = Math.min(100, 90 + Math.round((NECK_GOOD - neckMed) * 2));
        } else if (neckSt === 'poor' || torsoSt === 'poor') {
            status = 'poor'; message = 'Poor posture \u2014 needs correction';
            score = Math.max(20, 50 - Math.round(Math.max(neckMed - NECK_MODERATE, torsoMed - TORSO_MODERATE) * 2));
        } else {
            status = 'moderate'; message = 'Moderate posture \u2014 small corrections needed';
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
        savePostureResult(postureResult, currentUser?.id);
    }, [currentUser?.id]);

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
                color: 'rgba(34, 211, 238, 0.5)', lineWidth: 2,
            });
            drawingUtils.drawLandmarks(lm, { color: '#22d3ee', lineWidth: 1, radius: 3 });

            const w = canvas.width, h = canvas.height;
            const neck = calcAngle(lm[11].x * w, lm[11].y * h, lm[7].x * w, lm[7].y * h);
            const torso = calcAngle(lm[23].x * w, lm[23].y * h, lm[11].x * w, lm[11].y * h);

            setLiveNeck(Math.round(neck * 10) / 10);
            setLiveTorso(Math.round(torso * 10) / 10);

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

    useEffect(() => {
        let cancelled = false;

        async function init() {
            setLoadingMsg('Loading posture model...');
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

            setLoadingMsg('Starting camera...');
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' },
            });
            if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }
            streamRef.current = stream;

            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                videoRef.current.onloadeddata = () => {
                    if (cancelled) return;
                    setPhase('ready');
                    phaseRef.current = 'ready';
                    animFrameRef.current = requestAnimationFrame(runDetection);
                };
            }
        }

        init();
        return () => { cancelled = true; cleanup(); };
    }, [runDetection, cleanup]);

    // Prep countdown
    useEffect(() => {
        if (phase !== 'ready') return;
        setTimeLeft(PREP_DURATION);

        const interval = setInterval(() => {
            setTimeLeft(prev => {
                if (prev <= 1) {
                    clearInterval(interval);
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

    // Auto-return countdown after results
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

    useVoiceWebSocket(useCallback((data) => {
        if (data.navigate === 'idle') {
            cleanup();
            setView('idle');
        }
    }, [cleanup, setView]));

    const progress = phase === 'capturing' ? ((CAPTURE_DURATION - timeLeft) / CAPTURE_DURATION) * 100 : 0;

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center relative overflow-hidden select-none">

            {/* Loading */}
            {phase === 'loading' && (
                <div className="flex flex-col items-center animate-fade-in z-10">
                    <div className="relative w-16 h-16 mb-6">
                        <div className="absolute inset-0 rounded-full border-2 border-white/10" />
                        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-cyan-400/60 animate-spin" />
                    </div>
                    <p className="text-white/40 text-sm tracking-wide">{loadingMsg}</p>
                </div>
            )}

            {/* Camera + Canvas */}
            <div className={`relative ${phase === 'loading' ? 'opacity-0 absolute' : ''}`}
                style={{ width: 640, maxWidth: '100vw' }}>
                <video ref={videoRef} autoPlay playsInline muted
                    className="w-full rounded-2xl" style={{ transform: 'scaleX(-1)' }} />
                <canvas ref={canvasRef}
                    className="absolute top-0 left-0 w-full h-full rounded-2xl pointer-events-none"
                    style={{ transform: 'scaleX(-1)' }} />

                {/* Subtle vignette overlay */}
                <div className="absolute inset-0 rounded-2xl pointer-events-none"
                    style={{ boxShadow: 'inset 0 0 80px rgba(0,0,0,0.4)' }} />

                {/* Get Ready overlay */}
                {phase === 'ready' && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center rounded-2xl"
                        style={{ background: 'rgba(0,0,0,0.5)' }}>
                        <div className="w-4 h-4 rounded-full bg-cyan-400/60 animate-ping mb-6" />
                        <p className="text-white/90 text-lg font-light tracking-wide">Get into position</p>
                        <p className="text-white/35 text-xs mt-2 tracking-wide">Stand so your upper body is visible</p>
                        <div className="mt-8 text-cyan-400/70 font-mono text-4xl font-light">{timeLeft}</div>
                    </div>
                )}

                {/* Live angle HUD */}
                {phase === 'capturing' && (
                    <div className="absolute top-4 left-4 flex flex-col gap-2">
                        <div className="glass-subtle px-3 py-2 flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full" style={{ background: statusColor(getStatus(liveNeck, NECK_GOOD, NECK_MODERATE)) }} />
                            <span className="text-white/70 text-xs font-mono">Neck {liveNeck}\u00B0</span>
                        </div>
                        <div className="glass-subtle px-3 py-2 flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full" style={{ background: statusColor(getStatus(liveTorso, TORSO_GOOD, TORSO_MODERATE)) }} />
                            <span className="text-white/70 text-xs font-mono">Torso {liveTorso}\u00B0</span>
                        </div>
                    </div>
                )}

                {/* Progress bar */}
                {phase === 'capturing' && (
                    <div className="absolute bottom-0 left-0 right-0 p-4">
                        <div className="glass-subtle px-4 py-3">
                            <div className="flex justify-between items-center mb-2">
                                <span className="text-white/50 text-xs tracking-wide">Analyzing posture</span>
                                <span className="text-cyan-400/70 font-mono text-xs">{timeLeft}s</span>
                            </div>
                            <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
                                <div className="h-full rounded-full transition-all duration-300"
                                    style={{ width: `${progress}%`, background: 'linear-gradient(90deg, rgba(34,211,238,0.6), rgba(74,222,128,0.6))' }} />
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Results overlay */}
            {phase === 'results' && result && (
                <div className="absolute inset-0 bg-black/85 flex items-center justify-center p-8 animate-fade-in">
                    <div className="glass-panel p-8 max-w-lg w-full stagger-children">

                        {/* Score */}
                        <div className="flex flex-col items-center mb-6">
                            <div className="w-24 h-24 rounded-full flex items-center justify-center text-3xl font-light border-2"
                                style={{ borderColor: statusColor(result.status), color: statusColor(result.status) }}>
                                {result.score}
                            </div>
                            <p className="text-white/80 text-sm font-light mt-3 tracking-wide">{result.message}</p>
                            <p className="text-white/20 text-xs mt-1">{result.framesAnalyzed} frames analyzed</p>
                        </div>

                        {/* Angles */}
                        <div className="grid grid-cols-2 gap-3 mb-6">
                            <div className="glass-subtle p-4 text-center">
                                <p className="text-white/30 text-xs uppercase tracking-wider mb-1">Neck</p>
                                <p className="text-xl font-mono font-light" style={{ color: statusColor(result.neckStatus) }}>{result.neckAngle}\u00B0</p>
                                <p className="text-xs mt-1 uppercase tracking-wider" style={{ color: statusColor(result.neckStatus) }}>{result.neckStatus}</p>
                            </div>
                            <div className="glass-subtle p-4 text-center">
                                <p className="text-white/30 text-xs uppercase tracking-wider mb-1">Torso</p>
                                <p className="text-xl font-mono font-light" style={{ color: statusColor(result.torsoStatus) }}>{result.torsoAngle}\u00B0</p>
                                <p className="text-xs mt-1 uppercase tracking-wider" style={{ color: statusColor(result.torsoStatus) }}>{result.torsoStatus}</p>
                            </div>
                        </div>

                        {/* Recommendations */}
                        {result.recommendations.length > 0 && (
                            <div className="space-y-2 mb-6">
                                <p className="text-white/30 text-xs uppercase tracking-wider">Suggestions</p>
                                {result.recommendations.map((rec, i) => (
                                    <div key={i} className="flex items-start gap-2">
                                        <span className="text-cyan-400/50 mt-0.5 text-xs">\u2022</span>
                                        <span className="text-white/50 text-xs leading-relaxed">{rec}</span>
                                    </div>
                                ))}
                            </div>
                        )}

                        <p className="text-center text-white/10 text-xs tracking-wide">
                            Returning in {returnCountdown}s
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}
