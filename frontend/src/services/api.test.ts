import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
    checkHealth,
    triggerAnalysis,
    triggerDebugAnalysis,
    detectFace,
    enrollFace,
    recognizeFace,
} from './api';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

beforeEach(() => {
    mockFetch.mockReset();
});

function jsonResponse(body: unknown, ok = true) {
    return Promise.resolve({
        ok,
        json: () => Promise.resolve(body),
        text: () => Promise.resolve(JSON.stringify(body)),
    });
}

describe('checkHealth', () => {
    it('calls /health and returns parsed response', async () => {
        const payload = { status: 'ok', service: 'clarity-backend', thermal_enabled: false, weights: {} };
        mockFetch.mockReturnValueOnce(jsonResponse(payload));

        const result = await checkHealth();
        expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('/health'));
        expect(result).toEqual(payload);
    });

    it('throws when response is not ok', async () => {
        mockFetch.mockReturnValueOnce(jsonResponse({}, false));
        await expect(checkHealth()).rejects.toThrow('Backend unavailable');
    });
});

describe('triggerAnalysis', () => {
    it('calls POST /api/analyze with user_id', async () => {
        const payload = { id: '1', user_id: 'abc', scores: {}, overall_score: 85 };
        mockFetch.mockReturnValueOnce(jsonResponse(payload));

        const result = await triggerAnalysis('abc');
        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/analyze'),
            expect.objectContaining({
                method: 'POST',
                body: expect.stringContaining('"user_id":"abc"'),
            })
        );
        expect(result.overall_score).toBe(85);
    });

    it('throws when response is not ok', async () => {
        mockFetch.mockReturnValueOnce(jsonResponse({}, false));
        await expect(triggerAnalysis('abc')).rejects.toThrow('Analysis failed');
    });
});

describe('triggerDebugAnalysis', () => {
    it('sends image in body when provided', async () => {
        const payload = { success: true, scores: {}, overall_score: 70, captured_image: null, details: {}, errors: [], timing_ms: 100 };
        mockFetch.mockReturnValueOnce(jsonResponse(payload));

        await triggerDebugAnalysis('base64data');
        const call = mockFetch.mock.calls[0];
        expect(call[0]).toContain('/api/debug/analyze');
        expect(JSON.parse(call[1].body)).toEqual({ image: 'base64data' });
    });

    it('sends null image when not provided', async () => {
        const payload = { success: true, scores: {}, overall_score: 70, captured_image: null, details: {}, errors: [], timing_ms: 100 };
        mockFetch.mockReturnValueOnce(jsonResponse(payload));

        await triggerDebugAnalysis();
        const body = JSON.parse(mockFetch.mock.calls[0][1].body);
        expect(body.image).toBeNull();
    });

    it('throws with error text on failure', async () => {
        mockFetch.mockReturnValueOnce(Promise.resolve({
            ok: false,
            text: () => Promise.resolve('internal error'),
        }));
        await expect(triggerDebugAnalysis()).rejects.toThrow('Debug analysis failed: internal error');
    });
});

describe('detectFace', () => {
    it('sends base64 image and returns detection result', async () => {
        const payload = { face_detected: true, bbox: [10, 20, 100, 200], landmarks: [[1, 2]], latency_ms: 50 };
        mockFetch.mockReturnValueOnce(jsonResponse(payload));

        const result = await detectFace('img_b64');
        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/face/detect'),
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ image: 'img_b64' }),
            })
        );
        expect(result.face_detected).toBe(true);
    });

    it('throws on failure', async () => {
        mockFetch.mockReturnValueOnce(jsonResponse({}, false));
        await expect(detectFace('img')).rejects.toThrow('Face detection failed');
    });
});

describe('enrollFace', () => {
    it('sends name and images array', async () => {
        const payload = { success: true, user_id: 'uuid-1', name: 'Alice', quality_score: 0.95, faces_processed: 3, latency_ms: 120 };
        mockFetch.mockReturnValueOnce(jsonResponse(payload));

        const result = await enrollFace('Alice', ['img1', 'img2', 'img3']);
        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/face/enroll'),
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ name: 'Alice', images: ['img1', 'img2', 'img3'] }),
            })
        );
        expect(result.user_id).toBe('uuid-1');
    });

    it('throws with error text on failure', async () => {
        mockFetch.mockReturnValueOnce(Promise.resolve({
            ok: false,
            text: () => Promise.resolve('bad images'),
        }));
        await expect(enrollFace('Bob', [])).rejects.toThrow('Enrollment failed: bad images');
    });
});

describe('recognizeFace', () => {
    it('sends image and returns match result', async () => {
        const payload = { match: true, user_id: 'uuid-1', name: 'Alice', confidence: 0.92, match_type: 'strong', latency_ms: 80 };
        mockFetch.mockReturnValueOnce(jsonResponse(payload));

        const result = await recognizeFace('face_b64');
        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/face/recognize'),
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ image: 'face_b64' }),
            })
        );
        expect(result.match).toBe(true);
        expect(result.name).toBe('Alice');
    });

    it('throws on failure', async () => {
        mockFetch.mockReturnValueOnce(jsonResponse({}, false));
        await expect(recognizeFace('img')).rejects.toThrow('Face recognition failed');
    });
});
