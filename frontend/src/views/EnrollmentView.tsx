import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { GlassCard } from '../components/ui/GlassCard';
import { Button } from '../components/ui/Button';

type EnrollmentStep = 'welcome' | 'position' | 'capture' | 'name' | 'success';

export function EnrollmentView() {
    const { setView, setCurrentUser } = useApp();
    const [step, setStep] = useState<EnrollmentStep>('welcome');
    const [name, setName] = useState('');
    const [isCapturing, setIsCapturing] = useState(false);

    const handleCapture = async () => {
        setIsCapturing(true);
        // Simulate face capture delay
        await new Promise((resolve) => setTimeout(resolve, 2000));
        setIsCapturing(false);
        setStep('name');
    };

    const handleSubmit = async () => {
        if (!name.trim()) return;

        // In production: call createUser API with face embedding
        const newUser = {
            id: Date.now(),
            name: name.trim(),
            created_at: new Date().toISOString(),
        };

        setCurrentUser(newUser);
        setStep('success');
    };

    const handleComplete = () => {
        setView('analysis');
    };

    const handleCancel = () => {
        setView('idle');
    };

    return (
        <div className="min-h-screen bg-black flex items-center justify-center p-8">
            <GlassCard className="w-full max-w-md animate-fade-in">
                {/* Step: Welcome */}
                {step === 'welcome' && (
                    <div className="text-center">
                        <h1 className="text-3xl font-light text-white mb-4">
                            Welcome to Clarity+
                        </h1>
                        <p className="text-white/60 mb-8">
                            Let's create your profile for personalized wellness tracking.
                            Your data stays private and is stored locally.
                        </p>
                        <div className="flex flex-col gap-3">
                            <Button onClick={() => setStep('position')}>
                                Get Started
                            </Button>
                            <Button variant="secondary" onClick={handleCancel}>
                                Cancel
                            </Button>
                        </div>
                    </div>
                )}

                {/* Step: Position Face */}
                {step === 'position' && (
                    <div className="text-center">
                        <h2 className="text-2xl font-light text-white mb-4">
                            Position Your Face
                        </h2>
                        <div className="w-48 h-48 mx-auto mb-6 rounded-full border-2 border-dashed border-white/30 flex items-center justify-center">
                            <span className="text-6xl">👤</span>
                        </div>
                        <p className="text-white/60 mb-8">
                            Center your face in the frame and look directly at the mirror.
                        </p>
                        <div className="flex flex-col gap-3">
                            <Button onClick={() => setStep('capture')}>
                                I'm Ready
                            </Button>
                            <Button variant="secondary" onClick={() => setStep('welcome')}>
                                Back
                            </Button>
                        </div>
                    </div>
                )}

                {/* Step: Capture */}
                {step === 'capture' && (
                    <div className="text-center">
                        <h2 className="text-2xl font-light text-white mb-4">
                            Capture Your Face
                        </h2>
                        <div className="w-48 h-48 mx-auto mb-6 rounded-full border-2 border-cyan-400/50 flex items-center justify-center bg-cyan-400/10">
                            {isCapturing ? (
                                <div className="w-12 h-12 border-4 border-white/20 border-t-cyan-400 rounded-full animate-spin" />
                            ) : (
                                <span className="text-6xl">📸</span>
                            )}
                        </div>
                        <p className="text-white/60 mb-8">
                            {isCapturing
                                ? 'Capturing... Hold still...'
                                : 'Press the button below to capture your face.'}
                        </p>
                        <div className="flex flex-col gap-3">
                            <Button onClick={handleCapture} disabled={isCapturing}>
                                {isCapturing ? 'Capturing...' : 'Capture Now'}
                            </Button>
                            <Button
                                variant="secondary"
                                onClick={() => setStep('position')}
                                disabled={isCapturing}
                            >
                                Back
                            </Button>
                        </div>
                    </div>
                )}

                {/* Step: Enter Name */}
                {step === 'name' && (
                    <div className="text-center">
                        <h2 className="text-2xl font-light text-white mb-4">
                            What's Your Name?
                        </h2>
                        <div className="mb-6">
                            <input
                                type="text"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="Enter your name"
                                className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-cyan-400 text-center text-lg"
                                autoFocus
                            />
                        </div>
                        <p className="text-white/60 mb-8">
                            This helps us personalize your experience.
                        </p>
                        <div className="flex flex-col gap-3">
                            <Button onClick={handleSubmit} disabled={!name.trim()}>
                                Create Profile
                            </Button>
                            <Button variant="secondary" onClick={() => setStep('capture')}>
                                Back
                            </Button>
                        </div>
                    </div>
                )}

                {/* Step: Success */}
                {step === 'success' && (
                    <div className="text-center">
                        <div className="text-6xl mb-6">🎉</div>
                        <h2 className="text-2xl font-light text-white mb-4">
                            Welcome, {name}!
                        </h2>
                        <p className="text-white/60 mb-8">
                            Your profile has been created. Let's run your first wellness analysis!
                        </p>
                        <Button onClick={handleComplete}>
                            Start Analysis
                        </Button>
                    </div>
                )}

                {/* Progress indicator */}
                <div className="flex justify-center gap-2 mt-8">
                    {['welcome', 'position', 'capture', 'name', 'success'].map((s, i) => (
                        <div
                            key={s}
                            className={`w-2 h-2 rounded-full transition-colors ${step === s
                                    ? 'bg-cyan-400'
                                    : ['welcome', 'position', 'capture', 'name', 'success'].indexOf(step) > i
                                        ? 'bg-white/60'
                                        : 'bg-white/20'
                                }`}
                        />
                    ))}
                </div>
            </GlassCard>
        </div>
    );
}
