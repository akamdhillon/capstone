import { Clock } from '../components/Clock';
import { useApp } from '../context/AppContext';

export function IdleView() {
    const {
        triggerRecognition,
        systemStatus,
    } = useApp();

    const statusDotColor = (() => {
        if (triggerRecognition) return 'bg-cyan-400 animate-pulse';
        if (systemStatus === 'connected') return 'bg-white/20 animate-status-breathe';
        if (systemStatus === 'error') return 'bg-red-400/60';
        return 'bg-white/10';
    })();

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center relative select-none">

            {triggerRecognition && (
                <div className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center animate-fade-in">
                    <div className="w-4 h-4 rounded-full bg-cyan-400/60 animate-ping mb-6" />
                    <p className="text-white/90 text-lg font-light tracking-wide">Looking for you...</p>
                    <p className="text-white/40 text-sm mt-2 tracking-wide">Backend is capturing from camera</p>
                </div>
            )}

            <div className="animate-fade-in-slow">
                <Clock showDate />
            </div>

            <div className="absolute top-8 right-8 flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${statusDotColor} transition-colors duration-700`} />
            </div>
        </div>
    );
}
