import { useEffect, useState, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';
import { getDailySummary, type DailySummary } from '../services/api';

const AUTO_RETURN_SECONDS = 20;

export function DailySummaryView() {
    const { currentUser, setView } = useApp();
    const [summary, setSummary] = useState<DailySummary | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [countdown, setCountdown] = useState(AUTO_RETURN_SECONDS);

    useEffect(() => {
        getDailySummary(currentUser?.id)
            .then(setSummary)
            .catch(() => setSummary(null))
            .finally(() => setIsLoading(false));
    }, [currentUser?.id]);

    // Auto-return countdown
    useEffect(() => {
        if (isLoading) return;
        const interval = setInterval(() => {
            setCountdown((prev) => {
                if (prev <= 1) {
                    clearInterval(interval);
                    setView(currentUser ? 'dashboard' : 'idle');
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);
        return () => clearInterval(interval);
    }, [isLoading, setView, currentUser]);

    useVoiceWebSocket(useCallback((data) => {
        if (data.navigate === 'idle') setView('idle');
        if (data.navigate === 'dashboard') setView('dashboard');
    }, [setView]));

    const trendDisplay = (trend: string) => {
        if (trend === 'improving') return { symbol: '\u2191', color: 'text-emerald-400', text: 'Improving' };
        if (trend === 'declining') return { symbol: '\u2193', color: 'text-red-400', text: 'Declining' };
        if (trend === 'stable') return { symbol: '\u2192', color: 'text-white/50', text: 'Stable' };
        return { symbol: '\u2014', color: 'text-white/20', text: 'No data yet' };
    };

    if (isLoading) {
        return (
            <div className="min-h-screen bg-black flex items-center justify-center">
                <div className="flex flex-col items-center gap-4 animate-fade-in">
                    <div className="w-12 h-12 border-2 border-white/10 border-t-cyan-400/50 rounded-full animate-spin" />
                    <p className="text-white/30 text-sm tracking-wide">Loading summary...</p>
                </div>
            </div>
        );
    }

    const trend = trendDisplay(summary?.trend ?? 'no_data');
    const hasData = summary && summary.total_assessments > 0;

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center p-8 select-none">
            <div className="w-full max-w-md stagger-children">

                {/* Title */}
                <div className="text-center mb-10">
                    <p className="text-white/25 text-xs uppercase tracking-[0.2em] mb-2">Today's Summary</p>
                    <h1 className="text-2xl font-light text-white/80">
                        {currentUser?.name ?? 'Wellness'} Overview
                    </h1>
                </div>

                {hasData ? (
                    <>
                        {/* Main score */}
                        <div className="glass-panel p-8 text-center mb-6">
                            <p className="text-white/30 text-xs uppercase tracking-wider mb-3">Average Wellness</p>
                            <p className="text-5xl font-light text-white/90">
                                {Math.round(summary!.average_score!)}
                            </p>
                            <div className="mt-3 flex items-center justify-center gap-2">
                                <span className={`text-lg ${trend.color}`}>{trend.symbol}</span>
                                <span className={`text-sm ${trend.color}`}>{trend.text}</span>
                            </div>
                        </div>

                        {/* Stats grid */}
                        <div className="grid grid-cols-2 gap-3 mb-6">
                            <SummaryStat label="Assessments" value={String(summary!.total_assessments)} />
                            <SummaryStat
                                label="Latest Score"
                                value={summary!.latest?.score != null ? String(summary!.latest.score) : '--'}
                                subtext={summary!.latest?.status}
                            />
                        </div>

                        {/* Trend bar */}
                        <div className="glass-subtle p-4 flex items-center gap-4">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-lg ${
                                trend.color
                            } bg-white/5`}>
                                {trend.symbol}
                            </div>
                            <div>
                                <p className="text-white/70 text-sm">{trend.text}</p>
                                <p className="text-white/25 text-xs mt-0.5">Compared to previous sessions</p>
                            </div>
                        </div>
                    </>
                ) : (
                    <div className="glass-panel p-8 text-center">
                        <p className="text-white/30 text-sm">No assessments yet today</p>
                        <p className="text-white/15 text-xs mt-2">
                            Say "Hey Clarity, check my posture" to get started
                        </p>
                    </div>
                )}

                {/* Auto-return notice */}
                <p className="text-center text-white/10 text-xs mt-8 tracking-wide">
                    Returning in {countdown}s
                </p>
            </div>
        </div>
    );
}

function SummaryStat({ label, value, subtext }: { label: string; value: string; subtext?: string }) {
    return (
        <div className="glass-subtle p-5 text-center">
            <p className="text-white/30 text-xs uppercase tracking-wider mb-2">{label}</p>
            <p className="text-2xl font-light text-white/80">{value}</p>
            {subtext && (
                <p className="text-white/20 text-xs mt-1 capitalize">{subtext}</p>
            )}
        </div>
    );
}
