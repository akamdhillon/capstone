// API Service for Clarity+ Backend
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface AnalysisScores {
    skin: number | null;
    posture: number | null;
    eyes: number | null;
    thermal: number | null;
}

export interface AnalysisResult {
    id: number;
    user_id: number;
    timestamp: string;
    scores: AnalysisScores;
    overall_score: number;
    weights_used: Record<string, number>;
}

export interface User {
    id: number;
    name: string;
    created_at: string;
    current_streak?: number;
    longest_streak?: number;
    badges?: string[];
}

export interface HealthStatus {
    status: string;
    service: string;
    thermal_enabled: boolean;
    weights: Record<string, number>;
}

// Check backend health
export async function checkHealth(): Promise<HealthStatus> {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) throw new Error('Backend unavailable');
    return response.json();
}

// Trigger a new analysis
export async function triggerAnalysis(userId: number): Promise<AnalysisResult> {
    const response = await fetch(`${API_BASE_URL}/api/analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, capture_image: true }),
    });
    if (!response.ok) throw new Error('Analysis failed');
    return response.json();
}

// Get user by ID
export async function getUser(userId: number): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/api/users/${userId}`);
    if (!response.ok) throw new Error('User not found');
    return response.json();
}

// Create a new user
export async function createUser(name: string, faceEmbedding?: number[]): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/api/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, face_embedding: faceEmbedding }),
    });
    if (!response.ok) throw new Error('Failed to create user');
    return response.json();
}

// Get analysis history for a user
export async function getAnalysisHistory(userId: number): Promise<AnalysisResult[]> {
    const response = await fetch(`${API_BASE_URL}/api/analysis/history/${userId}`);
    if (!response.ok) throw new Error('Failed to get history');
    return response.json();
}
