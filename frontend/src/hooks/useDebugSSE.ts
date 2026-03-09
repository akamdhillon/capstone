import { useEffect, useRef } from 'react';
import { API_BASE_URL } from '../config';

export interface DebugEvent {
    type: 'progress' | 'frame';
    phase?: string;
    service?: string;
    message?: string;
    elapsed_ms?: number;
    detail?: Record<string, unknown>;
    image?: string;
    _time?: string;
}

type DebugEventHandler = (event: DebugEvent) => void;

const DEBUG_SSE_STORAGE_KEY = 'clarity_debug_mode';

export function getDebugMode(): boolean {
    try {
        return localStorage.getItem(DEBUG_SSE_STORAGE_KEY) === '1';
    } catch {
        return false;
    }
}

export function setDebugMode(enabled: boolean): void {
    try {
        localStorage.setItem(DEBUG_SSE_STORAGE_KEY, enabled ? '1' : '0');
    } catch {
        /* ignore */
    }
}

export function useDebugSSE(onEvent: DebugEventHandler, enabled: boolean) {
    const handlerRef = useRef(onEvent);
    handlerRef.current = onEvent;

    useEffect(() => {
        if (!enabled) return;

        const url = `${API_BASE_URL}/api/debug/sse`;
        const es = new EventSource(url);

        es.onmessage = (e: MessageEvent) => {
            try {
                const data = JSON.parse(e.data) as DebugEvent;
                handlerRef.current(data);
            } catch {
                /* ignore non-JSON */
            }
        };

        es.onerror = () => {
            es.close();
        };

        return () => es.close();
    }, [enabled]);
}
