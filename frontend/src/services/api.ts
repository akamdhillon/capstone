// API Service for Clarity+ Backend
const API_BASE_URL = 'http://localhost:8000';

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
    captured_image?: string;
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

// =============================================================================
// DEBUG/DEV FUNCTIONS
// =============================================================================

export interface DebugAnalysisResult {
    success: boolean;
    scores: {
        skin: number | null;
        posture: number | null;
        eyes: number | null;
        thermal: number | null;
    };
    overall_score: number | null;
    captured_image: string | null;
    details: {
        skin: Record<string, unknown> | null;
        posture: Record<string, unknown> | null;
        eyes: Record<string, unknown> | null;
        thermal: Record<string, unknown> | null;
    };
    errors: string[];
    timing_ms: number;
}

export interface BackendDebugInfo {
    platform: {
        system: string;
        python_version: string;
    };
    configuration: {
        jetson_ip: string;
        thermal_enabled: boolean;
        dev_mode: boolean;
    };
    jetson_connectivity: Record<string, { reachable: boolean; url: string }>;
    errors: Record<string, string> | null;
    all_services_reachable: boolean;
}

// Trigger debug analysis with optional webcam image
export async function triggerDebugAnalysis(image?: string): Promise<DebugAnalysisResult> {
    const response = await fetch(`${API_BASE_URL}/api/debug/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: image ?? null }),
    });
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Debug analysis failed: ${errorText}`);
    }
    return response.json();
}

// Get backend debug/connectivity info
export async function getBackendDebugInfo(): Promise<BackendDebugInfo> {
    const response = await fetch(`${API_BASE_URL}/api/debug`);
    if (!response.ok) throw new Error('Failed to get debug info');
    return response.json();
}


// =============================================================================
// FACE RECOGNITION API
// =============================================================================

export interface FaceDetectResult {
    face_detected: boolean;
    bbox: number[] | null;
    landmarks: number[][] | null;
    latency_ms: number;
}

export interface FaceEnrollResult {
    success: boolean;
    user_id: string;
    name: string;
    quality_score: number;
    faces_processed: number;
    latency_ms: number;
}

export interface FaceRecognizeResult {
    match: boolean;
    user_id: string | null;
    name: string | null;
    confidence: number;
    match_type: 'strong' | 'weak' | 'unknown' | 'no_face' | 'no_users';
    latency_ms: number;
    message?: string;
}

// Detect face in a base64 image
export async function detectFace(imageBase64: string): Promise<FaceDetectResult> {
    const response = await fetch(`${API_BASE_URL}/api/face/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageBase64 }),
    });
    if (!response.ok) throw new Error('Face detection failed');
    return response.json();
}

// Enroll a new face with name + images
export async function enrollFace(name: string, images: string[]): Promise<FaceEnrollResult> {
    const response = await fetch(`${API_BASE_URL}/api/face/enroll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, images }),
    });
    if (!response.ok) {
        const err = await response.text();
        throw new Error(`Enrollment failed: ${err}`);
    }
    return response.json();
}

// Recognize a face from a base64 image
export async function recognizeFace(imageBase64: string): Promise<FaceRecognizeResult> {
    const response = await fetch(`${API_BASE_URL}/api/face/recognize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageBase64 }),
    });
    if (!response.ok) throw new Error('Face recognition failed');
    return response.json();
}
