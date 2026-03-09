import React, { useEffect, useState } from 'react';
import { useVoiceState } from '../hooks/useVoiceWebSocket';

type VoiceStateType = 'IDLE' | 'LISTENING' | 'PROCESSING' | 'SPEAKING';

export const VoiceIndicator: React.FC = () => {
    const { voiceState, caption, transcript } = useVoiceState();
    const state = voiceState as VoiceStateType;
    const [visible, setVisible] = useState(false);
    const [displayCaption, setDisplayCaption] = useState<string | null>(null);

    useEffect(() => {
        // Keep overlay visible while we still have content to show (caption/transcript),
        // even if the backend returns to IDLE.
        const shouldShow = state !== 'IDLE' || !!transcript || !!displayCaption || !!caption;
        if (shouldShow) {
            setVisible(true);
            return;
        }
        const timer = setTimeout(() => setVisible(false), 600);
        return () => clearTimeout(timer);
    }, [state, transcript, displayCaption, caption]);

    useEffect(() => {
        if (caption) setDisplayCaption(caption);
    }, [caption]);

    if (!visible) return null;

    return (
        <>
            {/* Listening state: full-screen white vignette + transcript hint */}
            {state === 'LISTENING' && (
                <>
                    <div
                        className="fixed inset-0 z-40 pointer-events-none animate-vignette-pulse"
                        style={{
                            background:
                                'radial-gradient(ellipse at center, transparent 40%, rgba(255,255,255,0.12) 80%, rgba(255,255,255,0.25) 100%)',
                        }}
                    />
                    <div className="fixed bottom-12 left-1/2 -translate-x-1/2 z-50 glass-subtle px-4 py-2 text-white/50 text-xs tracking-wide">
                        Listening...
                    </div>
                </>
            )}

            {/* Processing / Speaking: top-center overlay */}
            {(state === 'PROCESSING' || state === 'SPEAKING') && (
                <div
                    className="fixed top-6 left-1/2 -translate-x-1/2 z-50 flex flex-col items-center gap-3 transition-all duration-500 opacity-100"
                >
                    {/* Processing state: pulsing ring + transcript */}
                    {state === 'PROCESSING' && (
                        <div className="flex flex-col items-center gap-3 animate-fade-in">
                            {transcript && (
                                <div className="glass-subtle px-4 py-2 text-white/50 text-xs italic max-w-md text-center truncate" title={transcript}>
                                    &ldquo;{transcript}&rdquo;
                                </div>
                            )}
                            <div className="relative w-10 h-10">
                                <div className="absolute inset-0 rounded-full border-2 border-cyan-400/30" />
                                <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-cyan-400 animate-spin" />
                                <div className="absolute inset-2 rounded-full bg-cyan-400/10" />
                            </div>
                            <div className="glass-subtle px-5 py-2 text-white/70 text-sm tracking-wide">
                                Thinking...
                            </div>
                        </div>
                    )}

                    {/* Speaking state: caption + transcript (what you said) */}
                    {state === 'SPEAKING' && (
                        <div className="flex flex-col items-center gap-3 animate-slide-down">
                            {transcript && (
                                <div className="glass-subtle px-4 py-2 text-white/50 text-xs italic max-w-md text-center truncate" title={transcript}>
                                    &ldquo;{transcript}&rdquo;
                                </div>
                            )}
                            <div className="w-3 h-3 rounded-full bg-emerald-400 animate-status-breathe" />
                            <div className="glass px-6 py-3 max-w-md text-center">
                                <p className="text-white/90 text-sm leading-relaxed">
                                    {displayCaption || 'Speaking...'}
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </>
    );
};
