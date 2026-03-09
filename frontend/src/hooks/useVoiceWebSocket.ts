import { useEffect, useRef, useCallback, useState } from 'react';
import { WS_BASE_URL } from '../config';

export interface VoiceMessage {
    navigate?: string;
    action?: string;
    state?: string;
    display_name?: string;
    user_id?: string;
    caption?: string;
    transcript?: string;
    greeting?: string;
    result?: Record<string, unknown>;
    captured_image?: string;
    scores?: Record<string, number>;
    overall_score?: number;
    match?: boolean;
    [key: string]: unknown;
}

type MessageHandler = (data: VoiceMessage) => void;

let sharedSocket: WebSocket | null = null;
let listeners = new Set<MessageHandler>();
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

function ensureConnection() {
    if (sharedSocket && (sharedSocket.readyState === WebSocket.OPEN || sharedSocket.readyState === WebSocket.CONNECTING)) {
        return;
    }

    sharedSocket = new WebSocket(`${WS_BASE_URL}/ws/voice`);

    sharedSocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data) as VoiceMessage;
            listeners.forEach((handler) => handler(data));
        } catch { /* ignore non-JSON */ }
    };

    sharedSocket.onclose = () => {
        sharedSocket = null;
        if (listeners.size > 0 && !reconnectTimer) {
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                if (listeners.size > 0) ensureConnection();
            }, 3000);
        }
    };

    sharedSocket.onerror = () => {
        sharedSocket?.close();
    };
}

function subscribe(handler: MessageHandler) {
    listeners.add(handler);
    ensureConnection();
    return () => {
        listeners.delete(handler);
        if (listeners.size === 0) {
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
            sharedSocket?.close();
            sharedSocket = null;
        }
    };
}

export function useVoiceWebSocket(onMessage: MessageHandler) {
    const handlerRef = useRef(onMessage);
    handlerRef.current = onMessage;

    useEffect(() => {
        const handler: MessageHandler = (data) => handlerRef.current(data);
        return subscribe(handler);
    }, []);
}

export function useVoiceState() {
    const [voiceState, setVoiceState] = useState<string>('IDLE');
    const [displayName, setDisplayName] = useState('');
    const [caption, setCaption] = useState<string | null>(null);
    const [transcript, setTranscript] = useState<string | null>(null);

    // Keep caption/transcript visible briefly after state returns to IDLE.
    const captionClearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const transcriptClearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const CAPTION_HOLD_MS = 4500;
    const TRANSCRIPT_HOLD_MS = 6500;

    useEffect(() => {
        return () => {
            if (captionClearTimerRef.current) clearTimeout(captionClearTimerRef.current);
            if (transcriptClearTimerRef.current) clearTimeout(transcriptClearTimerRef.current);
        };
    }, []);

    useVoiceWebSocket(useCallback((data: VoiceMessage) => {
        if (data.state) setVoiceState(data.state as string);
        if (data.display_name) setDisplayName(data.display_name as string);
        if (typeof data.caption === 'string') {
            if (captionClearTimerRef.current) clearTimeout(captionClearTimerRef.current);
            setCaption(data.caption);
        }
        if (typeof data.transcript === 'string') {
            if (transcriptClearTimerRef.current) clearTimeout(transcriptClearTimerRef.current);
            setTranscript(data.transcript);
        }

        // When voice returns to IDLE, keep the last caption/transcript around briefly.
        if (data.state === 'IDLE') {
            if (captionClearTimerRef.current) clearTimeout(captionClearTimerRef.current);
            captionClearTimerRef.current = setTimeout(() => setCaption(null), CAPTION_HOLD_MS);

            if (transcriptClearTimerRef.current) clearTimeout(transcriptClearTimerRef.current);
            transcriptClearTimerRef.current = setTimeout(() => setTranscript(null), TRANSCRIPT_HOLD_MS);
        } else if (typeof data.state === 'string') {
            // Any active state cancels pending clears.
            if (captionClearTimerRef.current) {
                clearTimeout(captionClearTimerRef.current);
                captionClearTimerRef.current = null;
            }
            if (transcriptClearTimerRef.current) {
                clearTimeout(transcriptClearTimerRef.current);
                transcriptClearTimerRef.current = null;
            }
        }
    }, []));

    return { voiceState, displayName, caption, transcript };
}
