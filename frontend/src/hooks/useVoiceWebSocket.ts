import { useEffect, useRef, useCallback, useState } from 'react';
import { WS_BASE_URL } from '../config';

export interface VoiceMessage {
    navigate?: string;
    action?: string;
    state?: string;
    display_name?: string;
    caption?: string;
    transcript?: string;
    greeting?: string;
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

    useVoiceWebSocket(useCallback((data: VoiceMessage) => {
        if (data.state) setVoiceState(data.state as string);
        if (data.display_name) setDisplayName(data.display_name as string);
        if (typeof data.caption === 'string') setCaption(data.caption);
        if (typeof data.transcript === 'string') setTranscript(data.transcript);
        if (data.state === 'IDLE') {
            setCaption(null);
            setTranscript(null);
        }
    }, []));

    return { voiceState, displayName, caption, transcript };
}
