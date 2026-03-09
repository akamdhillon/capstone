import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { GlassCard } from '../components/ui/GlassCard';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';

type EnrollmentStep = 'welcome' | 'capturing' | 'processing' | 'success';

const CAPTURE_STEPS = [
    { label: 'Look straight', instruction: 'Look directly at the mirror' },
    { label: 'Tilt down', instruction: 'Lower your chin slightly' },
    { label: 'Tilt up', instruction: 'Raise your chin slightly' },
];

export function EnrollmentView() {
    const { setView, setCurrentUser } = useApp();
    const [step, setStep] = useState<EnrollmentStep>('welcome');
    const [captureIndex, setCaptureIndex] = useState(0);
    const [enrollError, setEnrollError] = useState<string | null>(null);
    const [userName, setUserName] = useState<string | null>(null);

    useVoiceWebSocket((data) => {
        if (data.enrollment_result) {
            const r = data.enrollment_result as { success?: boolean; user_id?: string; name?: string };
            if (r.success && r.name) {
                setCurrentUser({
                    id: r.user_id ?? crypto.randomUUID(),
                    name: r.name,
                    created_at: new Date().toISOString(),
                });
                setUserName(r.name);
                setStep('success');
            } else {
                setEnrollError(r && !r.success ? 'Enrollment failed' : null);
            }
        }
        if (data.enrollment_step !== undefined) {
            setCaptureIndex(data.enrollment_step as number);
        }
        if (data.enrollment_start) {
            setStep('capturing');
            setCaptureIndex(0);
        }
    });

    useEffect(() => {
        if (step === 'welcome') {
            const timer = setTimeout(() => setStep('capturing'), 3000);
            return () => clearTimeout(timer);
        }
    }, [step]);

    useEffect(() => {
        if (step === 'success') {
            const timer = setTimeout(() => setView('dashboard'), 5000);
            return () => clearTimeout(timer);
        }
    }, [step, setView]);

    const currentStep = CAPTURE_STEPS[Math.min(captureIndex, CAPTURE_STEPS.length - 1)];

    return (
        <div className="min-h-screen bg-black flex items-center justify-center p-8 select-none">
            <GlassCard className="w-full max-w-lg animate-fade-in">
                {step === 'welcome' && (
                    <div className="text-center">
                        <h1 className="text-2xl font-light text-white/90 mb-2 tracking-wide">Welcome to Clarity+</h1>
                        <p className="text-white/40 text-sm mb-8 leading-relaxed">
                            Face enrollment is voice-guided. Say &quot;Hey Clarity, enroll my face&quot; and tell your name when asked.
                            The backend will capture your face from the mirror camera.
                        </p>
                        <p className="text-white/20 text-xs tracking-wide animate-breathe">Preparing...</p>
                    </div>
                )}

                {step === 'capturing' && (
                    <div className="text-center">
                        <h2 className="text-2xl font-light text-white mb-1">Face Capture</h2>
                        <p className="text-white/40 text-sm mb-6">
                            Step {Math.min(captureIndex + 1, CAPTURE_STEPS.length)} of {CAPTURE_STEPS.length}
                        </p>
                        <div className="relative mx-auto mb-6 rounded-2xl overflow-hidden bg-white/5 flex items-center justify-center" style={{ width: 320, height: 240 }}>
                            <p className="text-white/50 text-sm">Backend camera capturing</p>
                        </div>
                        <p className="text-white font-medium">{currentStep?.label ?? 'Position yourself'}</p>
                        <p className="text-white/50 text-sm">{currentStep?.instruction ?? ''}</p>
                        {enrollError && <p className="text-red-400 text-sm mt-4">{enrollError}</p>}
                    </div>
                )}

                {step === 'processing' && (
                    <div className="text-center py-8">
                        <div className="w-16 h-16 mx-auto mb-6 border-4 border-white/20 border-t-cyan-400 rounded-full animate-spin" />
                        <h2 className="text-2xl font-light text-white mb-2">Creating your profile…</h2>
                    </div>
                )}

                {step === 'success' && userName && (
                    <div className="text-center">
                        <div className="w-16 h-16 mx-auto mb-4 rounded-full border border-emerald-400/30 flex items-center justify-center">
                            <span className="text-emerald-400 text-2xl">✓</span>
                        </div>
                        <h2 className="text-xl font-light text-white/90 mb-2 tracking-wide">
                            Welcome, <span className="text-cyan-400">{userName}</span>
                        </h2>
                        <p className="text-white/40 text-sm mb-4">
                            Your profile is ready. The mirror will recognize you automatically.
                        </p>
                        <p className="text-white/20 text-xs tracking-wide animate-breathe">Going to dashboard shortly...</p>
                    </div>
                )}
            </GlassCard>
        </div>
    );
}
