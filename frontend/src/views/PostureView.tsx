import { useEffect, useState, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';

const PREP_DURATION = 5;
const RESULTS_DISPLAY_DURATION = 15;

function statusColor(status: string): string {
    if (status === 'good') return '#4ade80';
    if (status === 'moderate') return '#facc15';
    return '#f87171';
}

export function PostureView() {
    const { setView, currentUser } = useApp();
    const [phase, setPhase] = useState<'prep' | 'analyzing' | 'results'>('prep');
    const [timeLeft, setTimeLeft] = useState(PREP_DURATION);
    const [returnCountdown, setReturnCountdown] = useState(RESULTS_DISPLAY_DURATION);
    const [result, setResult] = useState<{
        score: number;
        status: string;
        neckAngle: number;
        torsoAngle: number;
        neckStatus: string;
        torsoStatus: string;
        recommendations: string[];
        framesAnalyzed: number;
    } | null>(null);

    useVoiceWebSocket(useCallback((data) => {
        if (data.navigate === 'posture' && data.result) {
            const r = data.result as Record<string, unknown>;
            setResult({
                score: (r.score as number) ?? 0,
                status: (r.status as string) ?? 'unknown',
                neckAngle: (r.neck_angle as number) ?? 0,
                torsoAngle: (r.torso_angle as number) ?? 0,
                neckStatus: (r.neck_status as string) ?? 'unknown',
                torsoStatus: (r.torso_status as string) ?? 'unknown',
                recommendations: (r.recommendations as string[]) ?? [],
                framesAnalyzed: (r.frames_analyzed as number) ?? 0,
            });
            setPhase('results');
        }
    }, []));

    // Prep countdown
    useEffect(() => {
        if (phase !== 'prep') return;
        setTimeLeft(PREP_DURATION);
        const interval = setInterval(() => {
            setTimeLeft((prev) => {
                if (prev <= 1) {
                    clearInterval(interval);
                    setPhase('analyzing');
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);
        return () => clearInterval(interval);
    }, [phase]);

    // When we move to analyzing, backend is already running - we just wait for result
    useEffect(() => {
        if (phase === 'analyzing' && !result) {
            // Keep showing "Analyzing..." until WebSocket delivers result
        }
    }, [phase, result]);

    const goHome = useCallback(() => {
        setView(currentUser ? 'dashboard' : 'idle');
    }, [setView, currentUser]);

    // Auto-return countdown after results
    useEffect(() => {
        if (phase !== 'results') return;
        setReturnCountdown(RESULTS_DISPLAY_DURATION);
        const interval = setInterval(() => {
            setReturnCountdown((prev) => {
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
            setView('idle');
        }
    }, [setView]));

    const message = phase === 'prep'
        ? 'Get into position'
        : phase === 'analyzing'
            ? 'Analyzing posture...'
            : '';

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center relative overflow-hidden select-none">
            {phase !== 'results' && (
                <div className="flex flex-col items-center animate-fade-in z-10">
                    <div className="relative w-16 h-16 mb-6">
                        <div className="absolute inset-0 rounded-full border-2 border-white/10" />
                        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-cyan-400/60 animate-spin" />
                    </div>
                    <p className="text-white/90 text-lg font-light tracking-wide">{message}</p>
                    {phase === 'prep' && (
                        <p className="text-white/35 text-xs mt-2 tracking-wide">Stand so your upper body is visible</p>
                    )}
                    {phase === 'prep' && (
                        <div className="mt-8 text-cyan-400/70 font-mono text-4xl font-light">{timeLeft}</div>
                    )}
                </div>
            )}

            {phase === 'results' && result && (
                <div className="absolute inset-0 bg-black/85 flex items-center justify-center p-8 animate-fade-in">
                    <div className="glass-panel p-8 max-w-lg w-full stagger-children">
                        <div className="flex flex-col items-center mb-6">
                            <div
                                className="w-24 h-24 rounded-full flex items-center justify-center text-3xl font-light border-2"
                                style={{ borderColor: statusColor(result.status), color: statusColor(result.status) }}
                            >
                                {result.score}
                            </div>
                            <p className="text-white/80 text-sm font-light mt-3 tracking-wide">
                                {result.status === 'good' ? 'Excellent posture! Keep it up.' : result.status === 'moderate' ? 'Moderate posture — small corrections needed' : 'Poor posture — needs correction'}
                            </p>
                            <p className="text-white/20 text-xs mt-1">{result.framesAnalyzed} frames analyzed</p>
                        </div>

                        <div className="grid grid-cols-2 gap-3 mb-6">
                            <div className="glass-subtle p-4 text-center">
                                <p className="text-white/30 text-xs uppercase tracking-wider mb-1">Neck</p>
                                <p className="text-xl font-mono font-light" style={{ color: statusColor(result.neckStatus) }}>{result.neckAngle}°</p>
                                <p className="text-xs mt-1 uppercase tracking-wider" style={{ color: statusColor(result.neckStatus) }}>{result.neckStatus}</p>
                            </div>
                            <div className="glass-subtle p-4 text-center">
                                <p className="text-white/30 text-xs uppercase tracking-wider mb-1">Torso</p>
                                <p className="text-xl font-mono font-light" style={{ color: statusColor(result.torsoStatus) }}>{result.torsoAngle}°</p>
                                <p className="text-xs mt-1 uppercase tracking-wider" style={{ color: statusColor(result.torsoStatus) }}>{result.torsoStatus}</p>
                            </div>
                        </div>

                        {result.recommendations.length > 0 && (
                            <div className="space-y-2 mb-6">
                                <p className="text-white/30 text-xs uppercase tracking-wider">Suggestions</p>
                                {result.recommendations.map((rec, i) => (
                                    <div key={i} className="flex items-start gap-2">
                                        <span className="text-cyan-400/50 mt-0.5 text-xs">•</span>
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
