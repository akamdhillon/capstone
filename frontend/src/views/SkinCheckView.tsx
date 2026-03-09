import { useEffect, useState, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';

const PREP_DURATION = 3;
const AUTO_RETURN_SECONDS = 20;

export function SkinCheckView() {
    const { setView, currentUser } = useApp();

    const [phase, setPhase] = useState<'prep' | 'analyzing' | 'results'>('prep');
    const [timeLeft, setTimeLeft] = useState(PREP_DURATION);
    const [returnCountdown, setReturnCountdown] = useState(AUTO_RETURN_SECONDS);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<{
        score?: number;
        details?: Record<string, unknown>;
        captured_image?: string;
        recommendation?: string;
    } | null>(null);

    useVoiceWebSocket(useCallback((data) => {
        if (data.navigate === 'skin' && data.result) {
            const r = data.result as Record<string, unknown>;
            if ((r as { error?: string }).error) {
                setError((r as { error: string }).error);
                setPhase('results');
                return;
            }
            setResult({
                score: r.score as number | undefined,
                details: r.details as Record<string, unknown> | undefined,
                captured_image: r.captured_image as string | undefined,
                recommendation: r.recommendation as string | undefined,
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

    const handleClose = useCallback(() => {
        setView(currentUser ? 'dashboard' : 'idle');
    }, [setView, currentUser]);

    // Auto-return countdown after results
    useEffect(() => {
        if (phase !== 'results') return;
        setReturnCountdown(AUTO_RETURN_SECONDS);
        const interval = setInterval(() => {
            setReturnCountdown((prev) => {
                if (prev <= 1) {
                    clearInterval(interval);
                    handleClose();
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);
        return () => clearInterval(interval);
    }, [phase, handleClose]);

    useVoiceWebSocket(useCallback((data) => {
        if (data.navigate === 'idle') setView('idle');
        if (data.navigate === 'dashboard') setView('dashboard');
    }, [setView]));

    const score = result?.score ?? null;
    const details = result?.details ?? {};
    const acneDetails = details?.acne as Record<string, unknown> | undefined;
    const classification = acneDetails?.classification ?? '--';
    const severity = acneDetails?.severity_score != null ? String(acneDetails.severity_score) : '--';
    const confidence = acneDetails?.confidence != null ? `${acneDetails.confidence}%` : '--';
    const recommendation = result?.recommendation;

    const scoreColor = score === null
        ? 'text-white/20'
        : score >= 80 ? 'text-emerald-400'
        : score >= 60 ? 'text-lime-400'
        : score >= 40 ? 'text-yellow-400'
        : 'text-red-400';

    const statusLabel = score === null ? '--'
        : score >= 80 ? 'Excellent'
        : score >= 60 ? 'Good'
        : score >= 40 ? 'Fair'
        : 'Poor';

    const message = phase === 'prep'
        ? 'Position your face in frame'
        : phase === 'analyzing'
            ? 'Analyzing skin...'
            : '';

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center p-8 select-none">
            {phase !== 'results' && (
                <div className="flex flex-col items-center animate-fade-in z-10">
                    <div className="relative w-16 h-16 mb-6">
                        <div className="absolute inset-0 rounded-full border-2 border-white/10" />
                        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-cyan-400/60 animate-spin" />
                    </div>
                    <p className="text-white/90 text-lg font-light tracking-wide">{message}</p>
                    {phase === 'prep' && (
                        <p className="text-white/35 text-xs mt-2 tracking-wide">Face the mirror for skin analysis</p>
                    )}
                    {phase === 'prep' && (
                        <div className="mt-8 text-cyan-400/70 font-mono text-4xl font-light">{timeLeft}</div>
                    )}
                </div>
            )}

            {phase === 'results' && (
                <div className="absolute inset-0 bg-black/85 flex items-center justify-center p-8 animate-fade-in">
                    {error ? (
                        <div className="flex flex-col items-center text-center">
                            <p className="text-red-400/80 text-sm mb-6">{error}</p>
                            <p className="text-white/20 text-xs">Returning in {returnCountdown}s</p>
                        </div>
                    ) : (
                        <div className="glass-panel p-8 max-w-lg w-full stagger-children">
                            <p className="text-white/25 text-xs uppercase tracking-[0.15em] mb-6">Skin Health Analysis</p>
                            <div className="flex flex-col items-center mb-6">
                                <div
                                    className="w-24 h-24 rounded-full flex flex-col items-center justify-center text-3xl font-light border-2"
                                    style={{
                                        borderColor: score !== null
                                            ? score >= 80 ? '#4ade80'
                                            : score >= 60 ? '#a3e635'
                                            : score >= 40 ? '#facc15'
                                            : '#f87171'
                                            : 'rgba(255,255,255,0.1)',
                                        color: score !== null
                                            ? (score >= 80 ? '#4ade80'
                                                : score >= 60 ? '#a3e635'
                                                : score >= 40 ? '#facc15'
                                                : '#f87171')
                                            : 'rgba(255,255,255,0.5)',
                                    }}
                                >
                                    {score !== null ? Math.round(score) : '—'}
                                </div>
                                <p className="text-white/80 text-sm font-light mt-3 tracking-wide">{statusLabel}</p>
                            </div>
                            <div className="glass-subtle px-6 py-3 mb-6 text-center">
                                <p className="text-white/30 text-xs uppercase tracking-wider mb-1">Classification</p>
                                <p className={`text-xl font-light ${scoreColor}`}>{String(classification)}</p>
                            </div>
                            <div className="grid grid-cols-2 gap-3 mb-6">
                                <div className="glass-subtle p-4 text-center">
                                    <p className="text-white/30 text-xs uppercase tracking-wider mb-1">Severity</p>
                                    <p className="text-white/70 text-lg font-light font-mono">{severity}</p>
                                    <p className="text-white/20 text-[10px] mt-0.5">out of 10</p>
                                </div>
                                <div className="glass-subtle p-4 text-center">
                                    <p className="text-white/30 text-xs uppercase tracking-wider mb-1">Confidence</p>
                                    <p className="text-white/70 text-lg font-light font-mono">{confidence}</p>
                                </div>
                            </div>
                            {recommendation && (
                                <div className="space-y-2 mb-6">
                                    <p className="text-white/30 text-xs uppercase tracking-wider">Recommendation</p>
                                    <p className="text-white/50 text-xs leading-relaxed">{recommendation}</p>
                                </div>
                            )}
                            {result?.captured_image && (
                                <div className="glass-subtle p-1 rounded-2xl overflow-hidden mb-6">
                                    <img src={`data:image/jpeg;base64,${result.captured_image}`} alt="Capture" className="w-48 h-auto rounded-xl mx-auto" />
                                </div>
                            )}
                            <p className="text-center text-white/10 text-xs tracking-wide">
                                Returning in {returnCountdown}s
                            </p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
