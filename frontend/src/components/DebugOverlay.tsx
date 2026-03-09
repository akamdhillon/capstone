import { useState, useCallback, useEffect } from 'react';
import { useDebugSSE, getDebugMode, setDebugMode, type DebugEvent } from '../hooks/useDebugSSE';

const MAX_PROGRESS_ITEMS = 50;

function phaseColor(phase: string): string {
    switch (phase) {
        case 'capturing': return '#60a5fa';
        case 'running': return '#facc15';
        case 'complete': return '#4ade80';
        case 'error': return '#f87171';
        default: return 'rgba(255,255,255,0.5)';
    }
}

export function DebugOverlay() {
    const [visible, setVisible] = useState(getDebugMode);
    const [progressLog, setProgressLog] = useState<DebugEvent[]>([]);
    const [latestFrame, setLatestFrame] = useState<string | null>(null);
    const [lastResult, setLastResult] = useState<DebugEvent | null>(null);
    const [showRawJson, setShowRawJson] = useState(false);

    const handleEvent = useCallback((event: DebugEvent) => {
        const now = new Date();
        const timeStr = now.toTimeString().slice(0, 8);
        const eventWithTime = { ...event, _time: timeStr };

        if (event.type === 'progress') {
            setProgressLog((prev) => {
                const next = [...prev, eventWithTime].slice(-MAX_PROGRESS_ITEMS);
                return next;
            });
            if (event.phase === 'complete' || event.phase === 'error') {
                setLastResult(eventWithTime);
            }
        }
        if (event.type === 'frame' && event.image) {
            setLatestFrame(event.image);
        }
    }, []);

    useDebugSSE(handleEvent, visible);

    const toggleVisible = useCallback(() => {
        const next = !visible;
        setVisible(next);
        setDebugMode(next);
        if (!next) {
            setProgressLog([]);
            setLatestFrame(null);
            setLastResult(null);
        }
    }, [visible]);

    useEffect(() => {
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'D') {
                e.preventDefault();
                toggleVisible();
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [toggleVisible]);

    const clearLog = useCallback(() => {
        setProgressLog([]);
        setLastResult(null);
    }, []);

    if (!visible) {
        return (
            <button
                type="button"
                onClick={toggleVisible}
                className="fixed bottom-4 right-4 z-50 px-3 py-2 text-xs font-mono bg-black/70 text-white/70 hover:text-white rounded border border-white/20"
            >
                Debug
            </button>
        );
    }

    return (
        <div className="fixed bottom-4 right-4 z-50 w-[360px] max-h-[85vh] flex flex-col bg-black/90 border border-white/20 rounded-lg overflow-hidden shadow-xl">
            <div className="flex items-center justify-between px-3 py-2 border-b border-white/10">
                <span className="text-xs font-mono text-white/80">Debug Overlay</span>
                <div className="flex gap-1">
                    <button
                        type="button"
                        onClick={clearLog}
                        className="px-2 py-1 text-[10px] text-white/60 hover:text-white"
                    >
                        Clear
                    </button>
                    <button
                        type="button"
                        onClick={toggleVisible}
                        className="px-2 py-1 text-[10px] text-white/60 hover:text-white"
                    >
                        ✕
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {/* Section A: Camera Preview */}
                <div>
                    <p className="text-[10px] uppercase tracking-wider text-white/40 mb-1">Camera</p>
                    <div className="w-full max-h-[180px] rounded bg-white/5 flex items-center justify-center overflow-hidden aspect-video">
                        {latestFrame ? (
                            <img
                                src={`data:image/jpeg;base64,${latestFrame}`}
                                alt="Camera"
                                className="w-full h-auto object-contain"
                            />
                        ) : (
                            <span className="text-white/30 text-xs">Waiting for frame...</span>
                        )}
                    </div>
                </div>

                {/* Section B: Progress Log */}
                <div>
                    <p className="text-[10px] uppercase tracking-wider text-white/40 mb-1">Progress Log</p>
                    <div className="max-h-[160px] overflow-y-auto space-y-1 font-mono text-[11px]">
                        {progressLog.length === 0 ? (
                            <span className="text-white/30">No events yet</span>
                        ) : (
                            progressLog.map((evt, i) => (
                                <div
                                    key={i}
                                    className="flex flex-wrap gap-1 items-start py-1 border-b border-white/5 last:border-0"
                                >
                                    <span className="text-white/40 shrink-0">{evt._time ?? '--'}</span>
                                    {evt.phase && (
                                        <span
                                            className="px-1 rounded text-[10px] shrink-0"
                                            style={{ color: phaseColor(evt.phase), backgroundColor: `${phaseColor(evt.phase)}20` }}
                                        >
                                            {evt.phase}
                                        </span>
                                    )}
                                    {evt.service && (
                                        <span className="text-cyan-400/80 shrink-0">{evt.service}</span>
                                    )}
                                    <span className="text-white/70">{evt.message ?? ''}</span>
                                    {evt.detail && Object.keys(evt.detail).length > 0 && (
                                        <details className="w-full">
                                            <summary className="text-white/40 cursor-pointer">detail</summary>
                                            <pre className="mt-1 p-2 bg-black/50 rounded text-[10px] overflow-x-auto text-white/60">
                                                {JSON.stringify(evt.detail, null, 2)}
                                            </pre>
                                        </details>
                                    )}
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Section C: Last Result Summary */}
                {lastResult && (lastResult.phase === 'complete' || lastResult.phase === 'error') && (
                    <div>
                        <div className="flex items-center justify-between mb-1">
                            <p className="text-[10px] uppercase tracking-wider text-white/40">Last Result</p>
                            <button
                                type="button"
                                onClick={() => setShowRawJson((x) => !x)}
                                className="text-[10px] text-white/40 hover:text-white"
                            >
                                {showRawJson ? 'Summary' : 'Raw JSON'}
                            </button>
                        </div>
                        <div className="rounded bg-white/5 p-2 font-mono text-[11px] overflow-x-auto">
                            {showRawJson ? (
                                <pre className="text-white/70 whitespace-pre-wrap break-all">
                                    {JSON.stringify(lastResult.detail ?? lastResult, null, 2)}
                                </pre>
                            ) : (
                                <DebugResultSummary event={lastResult} />
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

function DebugResultSummary({ event }: { event: DebugEvent }) {
    const d = (event.detail ?? {}) as Record<string, unknown>;
    const svc = event.service ?? 'unknown';

    if (svc === 'posture') {
        const neck = (d.neck && typeof d.neck === 'object' ? (d.neck as Record<string, unknown>) : null);
        const torso = (d.torso && typeof d.torso === 'object' ? (d.torso as Record<string, unknown>) : null);
        return (
            <div className="space-y-1 text-white/70">
                <p>Score: {d.score != null ? String(d.score) : '--'}</p>
                <p>
                    Neck: {(neck?.angle ?? d.neck_angle) != null ? String(neck?.angle ?? d.neck_angle) : '--'}° (
                    {(neck?.status ?? d.neck_status) != null ? String(neck?.status ?? d.neck_status) : '--'})
                </p>
                <p>
                    Torso: {(torso?.angle ?? d.torso_angle) != null ? String(torso?.angle ?? d.torso_angle) : '--'}° (
                    {(torso?.status ?? d.torso_status) != null ? String(torso?.status ?? d.torso_status) : '--'})
                </p>
                <p>Frames: {d.frames_analyzed != null ? String(d.frames_analyzed) : '--'}</p>
            </div>
        );
    }
    if (svc === 'skin') {
        const acne = (d.details as Record<string, unknown>)?.acne as Record<string, unknown> | undefined;
        return (
            <div className="space-y-1 text-white/70">
                <p>Score: {d.score != null ? String(d.score) : '--'}</p>
                <p>Classification: {acne?.classification != null ? String(acne.classification) : '--'}</p>
                <p>Severity: {acne?.severity_score != null ? String(acne.severity_score) : '--'}</p>
                <p>Confidence: {acne?.confidence != null ? String(acne.confidence) : '--'}%</p>
                {d.recommendation != null && <p className="text-white/50 text-[10px] truncate">{String(d.recommendation)}</p>}
            </div>
        );
    }
    if (svc === 'eyes') {
        const details = d.details as Record<string, unknown> | undefined;
        return (
            <div className="space-y-1 text-white/70">
                <p>Score: {d.score != null ? String(d.score) : '--'}</p>
                <p>EAR: {details?.ear != null ? String(details.ear) : '--'}</p>
                <p>Blink rate: {details?.blink_rate != null ? String(details.blink_rate) : '--'}</p>
                <p>Drowsiness: {details?.drowsiness != null ? String(details.drowsiness) : '--'}</p>
            </div>
        );
    }
    if (svc === 'full') {
        const s = d.scores as Record<string, number> | undefined;
        return (
            <div className="space-y-1 text-white/70">
                <p>Overall: {d.overall_score != null ? String(d.overall_score) : '--'}</p>
                <p>Skin: {s?.skin ?? '--'} | Posture: {s?.posture ?? '--'} | Eyes: {s?.eyes ?? '--'} | Thermal: {s?.thermal ?? '--'}</p>
            </div>
        );
    }
    if (event.phase === 'error') {
        return <p className="text-red-400/80">{event.message ?? 'Unknown error'}</p>;
    }
    return <pre className="text-white/60">{JSON.stringify(d, null, 2)}</pre>;
}
