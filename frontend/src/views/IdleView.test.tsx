import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { IdleView } from './IdleView';
import { AppProvider } from '../context/AppContext';

vi.mock('../services/api', () => ({
    detectFace: vi.fn(),
    recognizeFace: vi.fn(),
}));

vi.mock('../hooks/useVoiceWebSocket', () => ({
    useVoiceWebSocket: vi.fn(),
    useVoiceState: vi.fn(() => ({ voiceState: 'IDLE', displayName: '' })),
}));

function renderWithProvider() {
    return render(
        <AppProvider>
            <IdleView />
        </AppProvider>
    );
}

describe('IdleView', () => {
    it('renders "Recognize Me" button', () => {
        renderWithProvider();
        expect(screen.getByText('Recognize Me')).toBeInTheDocument();
    });

    it('renders "Check Posture" button', () => {
        renderWithProvider();
        expect(screen.getByText(/Check Posture/)).toBeInTheDocument();
    });

    it('renders enrollment link', () => {
        renderWithProvider();
        expect(screen.getByText(/New user\? Tap to enroll/)).toBeInTheDocument();
    });

    it('renders voice test button', () => {
        renderWithProvider();
        expect(screen.getByText(/Try Voice Mode/)).toBeInTheDocument();
    });

    it('renders identity prompt', () => {
        renderWithProvider();
        expect(screen.getByText(/Tap above to identify yourself/)).toBeInTheDocument();
    });
});
