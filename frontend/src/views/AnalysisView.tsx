import { useEffect, useState } from 'react';
import { useApp } from '../context/AppContext';
import { triggerDebugAnalysis } from '../services/api'; // Import debug trigger
import { WellnessScore } from '../components/WellnessScore';
import { MetricCard } from '../components/MetricCard';
import { GlassCard } from '../components/ui/GlassCard';

export function AnalysisView() {
    const { setView, scores, overallScore, capturedImage, setScores, currentUser } = useApp();
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Perform analysis on mount
    useEffect(() => {
        const performAnalysis = async () => {
            try {
                // Use debug analysis for now to bypass user requirement & ensure same results as DevPanel
                // const result = await triggerAnalysis(currentUser.id);
                const result = await triggerDebugAnalysis();

                // Map debug result to expected format if needed, but they are similar
                setScores(
                    result.scores,
                    result.overall_score,
                    result.captured_image
                );
            } catch (err) {
                console.error("Analysis failed:", err);
                setError("Failed to analyze. Check connection.");
                // Optional: set a fallback timeout to go back to idle if it fails hard
            } finally {
                setIsLoading(false);
            }
        };

        performAnalysis();
    }, [currentUser, setScores]);

    // Auto-return to idle after 60 seconds
    useEffect(() => {
        if (!isLoading && !error) {
            const timer = setTimeout(() => {
                // setView('idle');
                // setScores(null, null, null);
                // DISABLED auto-return for debugging so user can see results
            }, 60000);
            return () => clearTimeout(timer);
        }
    }, [isLoading, error, setView, setScores]);

    const handleClose = () => {
        setView('idle');
        setScores(null, null, null);
    };

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center p-8">
            {isLoading ? (
                // Loading state
                <div className="flex flex-col items-center animate-fade-in">
                    <div className="w-20 h-20 border-4 border-white/20 border-t-cyan-400 rounded-full animate-spin mb-6" />
                    <p className="text-white/60 text-lg">Analyzing Wellness...</p>
                </div>
            ) : error ? (
                // Error state
                <div className="flex flex-col items-center animate-fade-in text-center">
                    <div className="text-red-400 text-xl font-medium mb-4">{error}</div>
                    <button
                        onClick={handleClose}
                        className="px-6 py-2 bg-white/10 hover:bg-white/20 rounded-full text-white transition-colors"
                    >
                        Return Home
                    </button>
                </div>
            ) : (
                // Results
                <div className="flex flex-row gap-8 w-full max-w-5xl animate-fade-in items-start justify-center">

                    {/* Left Column: Image & Score */}
                    <div className="flex flex-col items-center gap-6">
                        {capturedImage && (
                            <GlassCard className="p-2 rounded-2xl border-white/10 overflow-hidden">
                                <img
                                    src={`data:image/jpeg;base64,${capturedImage}`}
                                    alt="Analysis Capture"
                                    className="w-80 h-auto rounded-xl shadow-2xl"
                                />
                            </GlassCard>
                        )}

                        <div className="flex flex-col items-center">
                            <span className="text-white/40 text-sm mb-2 uppercase tracking-widest">Wellness Score</span>
                            <WellnessScore score={overallScore ?? 0} size={300} />
                        </div>
                    </div>

                    {/* Right Column: Metrics */}
                    <div className="flex flex-col w-full max-w-md">
                        {currentUser && (
                            <div className="mb-6">
                                <h2 className="text-2xl font-light text-white">
                                    Hello, <span className="font-medium text-cyan-400">{currentUser.name}</span>
                                </h2>
                                <p className="text-white/40 text-sm">Here is your wellness breakdown based on real-time analysis.</p>
                            </div>
                        )}

                        <div className="space-y-3">
                            <MetricCard
                                label="Skin Health"
                                score={scores?.skin ?? null}
                                icon="✨"
                                detail="Hydration & Model analysis"
                            />
                            <MetricCard
                                label="Posture"
                                score={scores?.posture ?? null}
                                icon="🧘"
                                detail="Shoulder alignment check"
                            />
                            <MetricCard
                                label="Eye Strain"
                                score={scores?.eyes ?? null}
                                icon="👁️"
                                detail="Blink rate analysis"
                            />
                            <MetricCard
                                label="Thermal"
                                score={scores?.thermal ?? null}
                                icon="🌡️"
                                detail="Facial temperature distribution"
                                disabled={scores?.thermal === null}
                            />
                        </div>

                        <button
                            onClick={handleClose}
                            className="mt-8 self-start text-white/40 hover:text-white/60 transition-colors text-sm flex items-center gap-2"
                        >
                            <span className="text-lg">↩</span> Return to Mirror
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
