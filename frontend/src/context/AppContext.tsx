import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import type { AnalysisScores, User } from '../services/api';

export type ViewType = 'idle' | 'dashboard' | 'analysis' | 'enrollment' | 'posture' | 'summary' | 'eyes' | 'skin';
export type MirrorMode = 'manual' | 'auto';

interface AppState {
    currentView: ViewType;
    setView: (view: ViewType) => void;

    currentUser: User | null;
    setCurrentUser: (user: User | null) => void;

    scores: AnalysisScores | null;
    overallScore: number | null;
    capturedImage: string | null;
    setScores: (scores: AnalysisScores | null, overall: number | null, image?: string | null) => void;

    isAnalyzing: boolean;
    setIsAnalyzing: (analyzing: boolean) => void;

    error: string | null;
    setError: (error: string | null) => void;

    triggerRecognition: boolean;
    setTriggerRecognition: (trigger: boolean) => void;

    voiceCaption: string | null;
    setVoiceCaption: (caption: string | null) => void;

    greeting: string | null;
    setGreeting: (greeting: string | null) => void;

    mode: MirrorMode;
    setMode: (mode: MirrorMode) => void;

    faceDetected: boolean;
    setFaceDetected: (detected: boolean) => void;

    systemStatus: 'connected' | 'disconnected' | 'error';
    setSystemStatus: (status: 'connected' | 'disconnected' | 'error') => void;
}

const AppContext = createContext<AppState | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
    const [currentView, setCurrentView] = useState<ViewType>('idle');
    const [currentUser, setCurrentUser] = useState<User | null>(null);
    const [scores, setScoresState] = useState<AnalysisScores | null>(null);
    const [overallScore, setOverallScore] = useState<number | null>(null);
    const [capturedImage, setCapturedImage] = useState<string | null>(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [triggerRecognition, setTriggerRecognition] = useState(false);
    const [voiceCaption, setVoiceCaption] = useState<string | null>(null);
    const [greeting, setGreeting] = useState<string | null>(null);
    const [mode, setMode] = useState<MirrorMode>('manual');
    const [faceDetected, setFaceDetected] = useState(false);
    const [systemStatus, setSystemStatus] = useState<'connected' | 'disconnected' | 'error'>('connected');

    const setView = useCallback((view: ViewType) => {
        setCurrentView(view);
        setError(null);
    }, []);

    const setScores = useCallback((newScores: AnalysisScores | null, overall: number | null, image: string | null = null) => {
        setScoresState(newScores);
        setOverallScore(overall);
        setCapturedImage(image);
    }, []);

    const value: AppState = {
        currentView, setView,
        currentUser, setCurrentUser,
        scores, overallScore, capturedImage, setScores,
        isAnalyzing, setIsAnalyzing,
        error, setError,
        triggerRecognition, setTriggerRecognition,
        voiceCaption, setVoiceCaption,
        greeting, setGreeting,
        mode, setMode,
        faceDetected, setFaceDetected,
        systemStatus, setSystemStatus,
    };

    return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppState {
    const context = useContext(AppContext);
    if (context === undefined) {
        throw new Error('useApp must be used within an AppProvider');
    }
    return context;
}
