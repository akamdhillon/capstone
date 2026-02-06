import { Clock } from '../components/Clock';
// import { DevPanel } from '../components/DevPanel'; // Removed as requested
import { useApp } from '../context/AppContext';

export function IdleView() {
    const { setView } = useApp();

    const handleInteraction = () => {
        // For demo: clicking starts analysis
        // In production: face detection triggers this
        setView('analysis');
    };

    return (
        <div
            className="min-h-screen bg-black flex flex-col items-center justify-center cursor-pointer"
            onClick={handleInteraction}
        >
            {/* Clock */}
            <Clock showDate className="mb-16" />

            {/* Prompt */}
            <p className="text-white/30 text-xl animate-pulse-subtle tracking-wide">
                Approach mirror to begin
            </p>

            {/* Enrollment option */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    setView('enrollment');
                }}
                className="absolute bottom-8 text-white/20 hover:text-white/40 text-sm transition-colors"
            >
                New user? Tap to enroll
            </button>

            {/* Dev Panel - Debug capture button */}
            {/* <DevPanel /> */}
        </div>
    );
}

