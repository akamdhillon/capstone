import { useState } from 'react';
import { triggerDebugAnalysis, type DebugAnalysisResult } from '../services/api';

/**
 * DevPanel - Debug button and results panel for development testing.
 * Triggers Jetson camera capture and displays ML analysis results.
 */
export function DevPanel() {
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<DebugAnalysisResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isExpanded, setIsExpanded] = useState(false);

    const handleDevCapture = async () => {
        setIsLoading(true);
        setError(null);
        setResult(null);

        try {
            const analysisResult = await triggerDebugAnalysis();
            setResult(analysisResult);
            setIsExpanded(true);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
            setIsExpanded(true);
        } finally {
            setIsLoading(false);
        }
    };

    const getScoreColor = (score: number | null) => {
        if (score === null) return 'text-gray-500';
        if (score >= 80) return 'text-green-400';
        if (score >= 60) return 'text-yellow-400';
        return 'text-red-400';
    };

    return (
        <div className="fixed bottom-4 right-4 z-50">
            {/* Main dev button */}
            <button
                onClick={handleDevCapture}
                disabled={isLoading}
                className={`
                    w-14 h-14 rounded-full shadow-lg flex items-center justify-center
                    transition-all duration-200 hover:scale-105
                    ${isLoading
                        ? 'bg-gray-600 cursor-wait'
                        : 'bg-gradient-to-br from-purple-600 to-indigo-700 hover:from-purple-500 hover:to-indigo-600'
                    }
                `}
                title="Dev: Capture & Analyze from Jetson Camera"
            >
                {isLoading ? (
                    <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                    <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                )}
            </button>

            {/* Results panel */}
            {isExpanded && (result || error) && (
                <div className="absolute bottom-16 right-0 w-80 bg-black/90 backdrop-blur-lg border border-white/20 rounded-xl p-4 shadow-2xl">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-white font-semibold flex items-center gap-2">
                            <span className="text-purple-400">🔧</span> Debug Results
                        </h3>
                        <button
                            onClick={() => setIsExpanded(false)}
                            className="text-white/40 hover:text-white/80"
                        >
                            ✕
                        </button>
                    </div>

                    {/* Error display */}
                    {error && (
                        <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-3 mb-3">
                            <p className="text-red-400 text-sm font-medium">Error</p>
                            <p className="text-red-300 text-xs mt-1">{error}</p>
                        </div>
                    )}

                    {/* Results display */}
                    {result && (
                        <div className="space-y-3">
                            {/* Captured image */}
                            {result.captured_image && (
                                <div className="rounded-lg overflow-hidden border border-white/20">
                                    <img
                                        src={`data:image/jpeg;base64,${result.captured_image}`}
                                        alt="Captured from Jetson camera"
                                        className="w-full h-auto"
                                    />
                                </div>
                            )}

                            {/* Overall score */}
                            <div className="bg-white/5 rounded-lg p-3">
                                <div className="flex items-center justify-between">
                                    <span className="text-white/60 text-sm">Overall Score</span>
                                    <span className={`text-2xl font-bold ${getScoreColor(result.overall_score)}`}>
                                        {result.overall_score?.toFixed(0) ?? '—'}
                                    </span>
                                </div>
                            </div>

                            {/* Individual scores */}
                            <div className="grid grid-cols-3 gap-2">
                                {(['skin', 'posture', 'eyes'] as const).map((metric) => (
                                    <div key={metric} className="bg-white/5 rounded-lg p-2 text-center">
                                        <p className="text-white/40 text-xs uppercase">{metric}</p>
                                        <p className={`text-lg font-semibold ${getScoreColor(result.scores[metric])}`}>
                                            {result.scores[metric]?.toFixed(0) ?? '—'}
                                        </p>
                                    </div>
                                ))}
                            </div>

                            {/* Timing */}
                            <div className="text-white/40 text-xs">
                                ⏱ {result.timing_ms?.toFixed(0) ?? '?'}ms
                            </div>

                            {/* Errors from services */}
                            {result.errors && result.errors.length > 0 && (
                                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-2">
                                    <p className="text-yellow-400 text-xs font-medium mb-1">Service Errors:</p>
                                    {result.errors.map((err, i) => (
                                        <p key={i} className="text-yellow-300/80 text-xs">• {err}</p>
                                    ))}
                                </div>
                            )}

                            {/* Raw details toggle */}
                            <details className="text-xs">
                                <summary className="text-white/40 cursor-pointer hover:text-white/60">
                                    Show raw response
                                </summary>
                                <pre className="mt-2 bg-white/5 rounded p-2 text-white/60 overflow-auto max-h-32 text-[10px]">
                                    {JSON.stringify(result.details, null, 2)}
                                </pre>
                            </details>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
