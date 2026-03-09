import { useEffect, useState, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';
import { CircularProgress } from '../components/ui/CircularProgress';
import type { AnalysisScores } from '../services/api';

const AUTO_RETURN_SECONDS = 30;

function coerceScores(input: unknown): AnalysisScores | null {
    if (!input || typeof input !== 'object') return null;
    const s = input as Record<string, unknown>;
    const val = (k: keyof AnalysisScores): number | null => {
        const v = s[k];
        return typeof v === 'number' ? v : v === null ? null : null;
    };
    return { skin: val('skin'), posture: val('posture'), eyes: val('eyes'), thermal: val('thermal') };
}

export function AnalysisView() {
    const {
        setView, scores, overallScore, capturedImage,
        setScores, currentUser,
    } = useApp();

    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [countdown, setCountdown] = useState(AUTO_RETURN_SECONDS);
    const [skinDetails, setSkinDetails] = useState<Record<string, unknown> | null>(null);

    useVoiceWebSocket(useCallback((data) => {
        if (data.navigate === 'analysis' && data.result) {
            setIsLoading(false);
            const r = data.result as Record<string, unknown>;
            if (typeof r.error === 'string' && r.error) {
                setError(r.error);
                return;
            }
            const s = coerceScores(r.scores);
            setScores(s, (r.overall_score as number) ?? null, (r.captured_image as string) ?? null);
            setSkinDetails((r.details as Record<string, unknown>)?.skin as Record<string, unknown> ?? null);
        }
    }, [setScores]));

    useEffect(() => {
        if (!isLoading && !error) return;
        const interval = setInterval(() => {
            setCountdown((prev) => {
                if (prev <= 1) {
                    clearInterval(interval);
                    handleClose();
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);
        return () => clearInterval(interval);
    }, [isLoading, error]);

    const handleClose = () => {
        setView(currentUser ? 'dashboard' : 'idle');
        setScores(null, null, null);
    };

    useVoiceWebSocket(useCallback((data) => {
        if (data.navigate === 'idle') {
            setScores(null, null, null);
            setView('idle');
        }
        if (data.navigate === 'dashboard') setView('dashboard');
    }, [setView, setScores]));

    const getAcneLabel = () => {
        const acne = (skinDetails?.details as Record<string, unknown>)?.acne as Record<string, unknown> | undefined;
        return acne?.classification ? String(acne.classification) : undefined;
    };

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center p-8 select-none">
            {isLoading ? (
                <div className="flex flex-col items-center animate-fade-in">
                    <div className="relative w-20 h-20 mb-6">
                        <div className="absolute inset-0 rounded-full border-2 border-white/10" />
                        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-cyan-400/60 animate-spin" />
                    </div>
                    <p className="text-white/90 text-lg font-light tracking-wide">Position yourself in frame</p>
                    <p className="text-white/40 text-sm mt-2 tracking-wide">Full wellness scan capturing from backend camera...</p>
                </div>
            ) : error ? (
                <div className="flex flex-col items-center animate-fade-in text-center">
                    <p className="text-red-400/80 text-sm mb-6">{error}</p>
                    <p className="text-white/20 text-xs">Returning automatically...</p>
                </div>
            ) : (
                <div className="w-full max-w-3xl animate-fade-in">
                    <div className="flex flex-col lg:flex-row gap-10 items-center justify-center">
                        <div className="flex flex-col items-center gap-6">
                            {capturedImage && (
                                <div className="glass-subtle p-1 rounded-2xl overflow-hidden">
                                    <img
                                        src={`data:image/jpeg;base64,${capturedImage}`}
                                        alt="Capture"
                                        className="w-64 h-auto rounded-xl"
                                    />
                                </div>
                            )}
                            <div className="flex flex-col items-center">
                                <p className="text-white/25 text-xs uppercase tracking-[0.15em] mb-3">Wellness Score</p>
                                <CircularProgress value={overallScore ?? 0} size={180} strokeWidth={10} />
                            </div>
                        </div>

                        <div className="flex flex-col w-full max-w-sm stagger-children">
                            {currentUser && (
                                <div className="mb-6">
                                    <h2 className="text-xl font-light text-white/80">{currentUser.name}</h2>
                                    <p className="text-white/25 text-xs mt-1 tracking-wide">Full wellness analysis</p>
                                </div>
                            )}

                            <div className="space-y-2">
                                <MetricRow label="Skin Health" score={scores?.skin ?? null} detail={getAcneLabel()} />
                                <MetricRow label="Posture" score={scores?.posture ?? null} />
                                <MetricRow label="Eye Strain" score={scores?.eyes ?? null} />
                                <MetricRow label="Thermal" score={scores?.thermal ?? null} disabled={scores?.thermal === null} />
                            </div>

                            <p className="mt-8 text-white/10 text-xs tracking-wide">
                                Returning in {countdown}s
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

function MetricRow({
    label, score, detail, disabled = false,
}: {
    label: string; score: number | null; detail?: string; disabled?: boolean;
}) {
    const color = score === null
        ? 'text-white/15'
        : score >= 80 ? 'text-emerald-400'
        : score >= 60 ? 'text-lime-400'
        : score >= 40 ? 'text-yellow-400'
        : 'text-red-400';

    const statusLabel = score === null ? '--'
        : score >= 80 ? 'Excellent'
        : score >= 60 ? 'Good'
        : score >= 40 ? 'Fair'
        : 'Poor';

    return (
        <div className={`glass-subtle p-4 flex items-center justify-between ${disabled ? 'opacity-25' : ''}`}>
            <div>
                <p className="text-white/70 text-sm">{label}</p>
                {detail && <p className="text-white/25 text-xs mt-0.5">{detail}</p>}
            </div>
            <div className="text-right">
                <span className={`text-2xl font-light ${color}`}>
                    {score !== null ? Math.round(score) : '—'}
                </span>
                <p className={`text-xs ${color} opacity-70`}>{statusLabel}</p>
            </div>
        </div>
    );
}
