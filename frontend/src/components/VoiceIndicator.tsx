import React from 'react';
import { useVoiceState } from '../hooks/useVoiceWebSocket';

type VoiceStateType = 'IDLE' | 'LISTENING' | 'PROCESSING' | 'SPEAKING';

export const VoiceIndicator: React.FC = () => {
    const { voiceState, displayName: userName } = useVoiceState();
    const state = voiceState as VoiceStateType;

    if (state === 'IDLE') return null;

    const getStatusColor = () => {
        switch (state) {
            case 'LISTENING': return 'bg-red-500 shadow-[0_0_20px_rgba(239,68,68,0.6)]';
            case 'PROCESSING': return 'bg-blue-500 animate-pulse shadow-[0_0_20px_rgba(59,130,246,0.6)]';
            case 'SPEAKING': return 'bg-green-500 shadow-[0_0_20px_rgba(34,197,94,0.6)]';
            default: return 'bg-gray-500';
        }
    };

    const getStatusText = () => {
        switch (state) {
            case 'LISTENING': return 'Clarity+ is listening...';
            case 'PROCESSING': return 'Thinking...';
            case 'SPEAKING': return `${userName || 'Clarity+'} is speaking`;
            default: return '';
        }
    };

    return (
        <div className="fixed top-8 left-1/2 -translate-x-1/2 z-50 flex flex-col items-center gap-3 transition-opacity duration-500">
            <div className={`w-4 h-4 rounded-full ${getStatusColor()} transition-colors duration-300`} />
            <div className="bg-black/60 backdrop-blur-md px-6 py-2 rounded-full border border-white/10 text-white text-sm font-medium tracking-wide shadow-2xl">
                {getStatusText()}
            </div>

            {state === 'LISTENING' && (
                <div className="flex gap-1 items-center justify-center">
                    {[1, 2, 3, 4, 5].map((i) => (
                        <div
                            key={i}
                            className="w-1 bg-white/40 rounded-full animate-voice-bar"
                            style={{
                                height: `${Math.random() * 20 + 10}px`,
                                animationDelay: `${i * 0.1}s`
                            }}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};
