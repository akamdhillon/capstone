import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import type { AnalysisScores, User } from '../services/api';

// View types
export type ViewType = 'idle' | 'analysis' | 'enrollment';

// App state interface
interface AppState {
    // Current view
    currentView: ViewType;
    setView: (view: ViewType) => void;

    // Current user
    currentUser: User | null;
    setCurrentUser: (user: User | null) => void;

    // Analysis scores
    scores: AnalysisScores | null;
    overallScore: number | null;
    setScores: (scores: AnalysisScores | null, overall: number | null) => void;

    // Loading state
    isAnalyzing: boolean;
    setIsAnalyzing: (analyzing: boolean) => void;

    // Error state
    error: string | null;
    setError: (error: string | null) => void;
}

// Create context
const AppContext = createContext<AppState | undefined>(undefined);

// Provider component
export function AppProvider({ children }: { children: ReactNode }) {
    const [currentView, setCurrentView] = useState<ViewType>('idle');
    const [currentUser, setCurrentUser] = useState<User | null>(null);
    const [scores, setScoresState] = useState<AnalysisScores | null>(null);
    const [overallScore, setOverallScore] = useState<number | null>(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const setView = useCallback((view: ViewType) => {
        setCurrentView(view);
        setError(null);
    }, []);

    const setScores = useCallback((newScores: AnalysisScores | null, overall: number | null) => {
        setScoresState(newScores);
        setOverallScore(overall);
    }, []);

    const value: AppState = {
        currentView,
        setView,
        currentUser,
        setCurrentUser,
        scores,
        overallScore,
        setScores,
        isAnalyzing,
        setIsAnalyzing,
        error,
        setError,
    };

    return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

// Hook to use the context
export function useApp(): AppState {
    const context = useContext(AppContext);
    if (context === undefined) {
        throw new Error('useApp must be used within an AppProvider');
    }
    return context;
}
