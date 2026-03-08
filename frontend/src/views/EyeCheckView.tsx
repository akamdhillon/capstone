import { useEffect, useState, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';
import { triggerEyeAnalysis, type SingleServiceResult } from '../services/api';

const AUTO_RETURN_SECONDS = 20;

export function EyeCheckView() {
    const { setView, currentUser, webcamFrame, setWebcamFrame } = useApp();

    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<SingleServiceResult | null>(null);
    const [countdown, setCountdown] = useState(AUTO_RETURN_SECONDS);

    useEffect(() => {
        const runAnalysis = async () => {
            try {
                const data = await triggerEyeAnalysis(webcamFrame ?? undefined);
                setResult(data);
            } catch (err) {
                console.error('Eye analysis failed:', err);
                setError('Eye analysis unavailable');
            } finally {
                setWebcamFrame(null);
                setIsLoading(false);
            }
        };
        runAnalysis();
    }, [webcamFrame, setWebcamFrame]);

    // Auto-return countdown
    useEffect(() => {
        if (isLoading || error) return;
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
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isLoading, error]);

    const handleClose = () => {
        setView(currentUser ? 'dashboard' : 'idle');
    };

    useVoiceWebSocket(useCallback((data) => {
        if (data.navigate === 'idle') setView('idle');
        if (data.navigate === 'dashboard') setView('dashboard');
    }, [setView]));

    const score = result?.score ?? null;
    const details = result?.details as Record<string, unknown> | null;
    const blinkRate = details?.blink_rate ?? '--';
    const drowsiness = details?.drowsiness ?? '--';

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

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center p-8 select-none">
            {isLoading ? (
                <div className="flex flex-col items-center animate-fade-in">
                    <div className="relative w-20 h-20 mb-6">
                        <div className="absolute inset-0 rounded-full border-2 border-white/10" />
                        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-cyan-400/60 animate-spin" />
                    </div>
                    <p className="text-white/40 text-sm tracking-wide">Analyzing eye strain...</p>
                </div>
            ) : error ? (
                <div className="flex flex-col items-center animate-fade-in text-center">
                    <p className="text-red-400/80 text-sm mb-6">{error}</p>
                    <p className="text-white/20 text-xs">Returning automatically...</p>
                </div>
            ) : (
                <div className="w-full max-w-md animate-fade-in">
                    <div className="flex flex-col items-center stagger-children">

                        {/* Title */}
                        <p className="text-white/25 text-xs uppercase tracking-[0.15em] mb-8">
                            Eye Strain Analysis
                        </p>

                        {/* Score circle */}
                        <div className="w-36 h-36 rounded-full flex flex-col items-center justify-center border-2 mb-8"
                            style={{
                                borderColor: score !== null
                                    ? score >= 80 ? '#4ade80'
                                        : score >= 60 ? '#a3e635'
                                            : score >= 40 ? '#facc15'
                                                : '#f87171'
                                    : 'rgba(255,255,255,0.1)',
                            }}>
                            <span className={`text-4xl font-light ${scoreColor}`}>
                                {score !== null ? Math.round(score) : '\u2014'}
                            </span>
                            <span className={`text-xs mt-1 ${scoreColor} opacity-70`}>{statusLabel}</span>
                        </div>

                        {/* Detail cards */}
                        <div className="w-full grid grid-cols-2 gap-3 mb-8">
                            <div className="glass-subtle p-4 text-center">
                                <p className="text-white/30 text-xs uppercase tracking-wider mb-1">Blink Rate</p>
                                <p className="text-white/70 text-lg font-light font-mono">{String(blinkRate)}</p>
                            </div>
                            <div className="glass-subtle p-4 text-center">
                                <p className="text-white/30 text-xs uppercase tracking-wider mb-1">Drowsiness</p>
                                <p className="text-white/70 text-lg font-light">{String(drowsiness)}</p>
                            </div>
                        </div>

                        {/* Captured image */}
                        {result?.captured_image && (
                            <div className="glass-subtle p-1 rounded-2xl overflow-hidden mb-6">
                                <img
                                    src={`data:image/jpeg;base64,${result.captured_image}`}
                                    alt="Capture"
                                    className="w-48 h-auto rounded-xl"
                                />
                            </div>
                        )}

                        <p className="text-white/10 text-xs tracking-wide">
                            Returning in {countdown}s
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}
