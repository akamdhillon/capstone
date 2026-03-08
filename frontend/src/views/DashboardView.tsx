import { useEffect, useState, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';
import { getDailySummary, getPostureResults, type DailySummary, type PostureResultEntry } from '../services/api';
import { CircularProgress } from '../components/ui/CircularProgress';

const SESSION_TIMEOUT = 30_000;

export function DashboardView() {
    const { currentUser, setView, greeting, setGreeting } = useApp();
    const [summary, setSummary] = useState<DailySummary | null>(null);
    const [latestPosture, setLatestPosture] = useState<PostureResultEntry | null>(null);
    const [showGreeting, setShowGreeting] = useState(!!greeting);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        async function fetchData() {
            try {
                const [summaryData, postureData] = await Promise.all([
                    getDailySummary(currentUser?.id).catch(() => null),
                    getPostureResults().catch(() => []),
                ]);
                setSummary(summaryData);
                if (postureData.length > 0) {
                    setLatestPosture(postureData[postureData.length - 1]);
                }
            } finally {
                setIsLoading(false);
            }
        }
        fetchData();
    }, [currentUser?.id]);

    // Greeting auto-dismiss
    useEffect(() => {
        if (showGreeting) {
            const timer = setTimeout(() => {
                setShowGreeting(false);
                setGreeting(null);
            }, 4000);
            return () => clearTimeout(timer);
        }
    }, [showGreeting, setGreeting]);

    // Session timeout — return to idle if no interaction
    useEffect(() => {
        const timer = setTimeout(() => setView('idle'), SESSION_TIMEOUT);
        return () => clearTimeout(timer);
    }, [setView]);

    useVoiceWebSocket(useCallback((data) => {
        if (data.navigate === 'idle') setView('idle');
    }, [setView]));

    const trendIcon = (trend: string) => {
        if (trend === 'improving') return { symbol: '\u2191', color: 'text-emerald-400', label: 'Improving' };
        if (trend === 'declining') return { symbol: '\u2193', color: 'text-red-400', label: 'Declining' };
        if (trend === 'stable') return { symbol: '\u2192', color: 'text-white/40', label: 'Stable' };
        return { symbol: '\u2014', color: 'text-white/20', label: 'No data' };
    };

    const wellnessScore = summary?.average_score ?? 0;
    const trend = trendIcon(summary?.trend ?? 'no_data');

    if (isLoading) {
        return (
            <div className="min-h-screen bg-black flex items-center justify-center">
                <div className="flex flex-col items-center gap-4 animate-fade-in">
                    <div className="w-12 h-12 border-2 border-white/10 border-t-cyan-400/50 rounded-full animate-spin" />
                    <p className="text-white/30 text-sm tracking-wide">Loading dashboard...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center p-8 relative select-none">

            {/* Greeting overlay */}
            {showGreeting && greeting && (
                <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/60 animate-fade-in">
                    <div className="text-center animate-slide-up">
                        <p className="text-3xl font-light text-white/90 tracking-wide">
                            {greeting}
                        </p>
                        <div className="mt-4 mx-auto w-12 h-[1px] bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent" />
                    </div>
                </div>
            )}

            {/* Main dashboard content */}
            <div className="w-full max-w-2xl stagger-children">

                {/* User name + time-of-day */}
                <div className="text-center mb-10">
                    <h1 className="text-2xl font-light text-white/80 tracking-wide">
                        {currentUser?.name ?? 'Guest'}
                    </h1>
                    <div className="mt-2 flex items-center justify-center gap-2">
                        <span className={`text-sm ${trend.color}`}>{trend.symbol}</span>
                        <span className="text-white/30 text-xs tracking-wider uppercase">{trend.label}</span>
                    </div>
                </div>

                {/* Wellness Score — large circle */}
                <div className="flex justify-center mb-12">
                    <CircularProgress value={wellnessScore} size={200} strokeWidth={10} />
                </div>

                {/* Subscore cards */}
                <div className="grid grid-cols-2 gap-3 mb-10">
                    <ScoreCard
                        label="Skin"
                        score={summary?.latest?.score ?? null}
                        sublabel="Health"
                    />
                    <ScoreCard
                        label="Posture"
                        score={latestPosture?.score ?? null}
                        sublabel={latestPosture?.status ?? undefined}
                    />
                    <ScoreCard
                        label="Eyes"
                        score={null}
                        sublabel="Strain check"
                    />
                    <ScoreCard
                        label="Thermal"
                        score={null}
                        sublabel="Face scan"
                        disabled
                    />
                </div>

                {/* Quick stats bar */}
                {summary && summary.total_assessments > 0 && (
                    <div className="glass-subtle p-4 flex items-center justify-around text-center">
                        <Stat label="Assessments" value={String(summary.total_assessments)} />
                        <div className="w-[1px] h-8 bg-white/5" />
                        <Stat label="Average" value={summary.average_score != null ? String(Math.round(summary.average_score)) : '--'} />
                        <div className="w-[1px] h-8 bg-white/5" />
                        <Stat label="Latest" value={summary.latest?.score != null ? String(summary.latest.score) : '--'} />
                    </div>
                )}
            </div>


        </div>
    );
}

function ScoreCard({
    label, score, sublabel, disabled = false,
}: {
    label: string; score: number | null; sublabel?: string; disabled?: boolean;
}) {
    const color = score === null
        ? 'text-white/20'
        : score >= 80 ? 'text-emerald-400'
            : score >= 60 ? 'text-lime-400'
                : score >= 40 ? 'text-yellow-400'
                    : 'text-red-400';

    return (
        <div className={`glass-subtle p-5 ${disabled ? 'opacity-30' : ''}`}>
            <p className="text-white/40 text-xs uppercase tracking-wider mb-1">{label}</p>
            <div className="flex items-end justify-between">
                <span className={`text-3xl font-light ${color}`}>
                    {score !== null ? Math.round(score) : '\u2014'}
                </span>
                {sublabel && (
                    <span className="text-white/20 text-xs capitalize">{sublabel}</span>
                )}
            </div>
        </div>
    );
}

function Stat({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <p className="text-white/60 text-lg font-light">{value}</p>
            <p className="text-white/25 text-[10px] uppercase tracking-wider mt-0.5">{label}</p>
        </div>
    );
}
