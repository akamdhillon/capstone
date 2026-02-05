import React, { useEffect, useState } from 'react';
import { useApp } from '../context/AppContext';
import { WellnessScore } from '../components/WellnessScore';
import { MetricCard } from '../components/MetricCard';
import { GlassCard } from '../components/ui/GlassCard';

export function AnalysisView() {
    const { setView, scores, overallScore, setScores, currentUser } = useApp();
    const [isLoading, setIsLoading] = useState(true);

    // Simulate analysis on mount (in production, this calls the backend)
    useEffect(() => {
        const performAnalysis = async () => {
            setIsLoading(true);

            // Simulate API delay
            await new Promise((resolve) => setTimeout(resolve, 1500));

            // Demo scores (in production, these come from the backend)
            const demoScores = {
                skin: 72 + Math.random() * 20,
                posture: 65 + Math.random() * 25,
                eyes: 58 + Math.random() * 30,
                thermal: null, // Disabled
            };

            // Calculate overall (weighted without thermal)
            const overall =
                demoScores.skin * 0.4 +
                demoScores.posture * 0.35 +
                demoScores.eyes * 0.25;

            setScores(demoScores, overall);
            setIsLoading(false);
        };

        performAnalysis();
    }, [setScores]);

    // Auto-return to idle after 30 seconds
    useEffect(() => {
        if (!isLoading) {
            const timer = setTimeout(() => {
                setView('idle');
                setScores(null, null);
            }, 30000);
            return () => clearTimeout(timer);
        }
    }, [isLoading, setView, setScores]);

    const handleClose = () => {
        setView('idle');
        setScores(null, null);
    };

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center p-8">
            {isLoading ? (
                // Loading state
                <div className="flex flex-col items-center animate-fade-in">
                    <div className="w-20 h-20 border-4 border-white/20 border-t-cyan-400 rounded-full animate-spin mb-6" />
                    <p className="text-white/60 text-lg">Analyzing...</p>
                </div>
            ) : (
                // Results
                <div className="flex flex-col items-center w-full max-w-md animate-fade-in">
                    {/* User greeting */}
                    {currentUser && (
                        <p className="text-white/50 text-lg mb-4">
                            Hello, {currentUser.name}
                        </p>
                    )}

                    {/* Main score */}
                    <WellnessScore score={overallScore ?? 0} className="mb-10" />

                    {/* Metric cards */}
                    <div className="w-full space-y-3">
                        <MetricCard
                            label="Skin Health"
                            score={scores?.skin ?? null}
                            icon="✨"
                            detail="Hydration & clarity"
                        />
                        <MetricCard
                            label="Posture"
                            score={scores?.posture ?? null}
                            icon="🧘"
                            detail="Alignment check"
                        />
                        <MetricCard
                            label="Eye Strain"
                            score={scores?.eyes ?? null}
                            icon="👁️"
                            detail="Blink rate & fatigue"
                        />
                    </div>

                    {/* Close button */}
                    <button
                        onClick={handleClose}
                        className="mt-8 text-white/40 hover:text-white/60 transition-colors text-sm"
                    >
                        Tap anywhere to dismiss
                    </button>
                </div>
            )}
        </div>
    );
}
