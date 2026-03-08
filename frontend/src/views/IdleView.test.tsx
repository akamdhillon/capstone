import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { IdleView } from './IdleView';
import { AppProvider } from '../context/AppContext';

vi.mock('../services/api', () => ({
    detectFace: vi.fn(),
    recognizeFace: vi.fn(),
}));

vi.mock('../hooks/useVoiceWebSocket', () => ({
    useVoiceWebSocket: vi.fn(),
    useVoiceState: vi.fn(() => ({ voiceState: 'IDLE', displayName: '', caption: null })),
}));

function renderWithProvider() {
    return render(
        <AppProvider>
            <IdleView />
        </AppProvider>
    );
}

describe('IdleView', () => {
    it('renders the clock', () => {
        const { container } = renderWithProvider();
        // Clock displays a time string with AM/PM
        expect(container.textContent).toMatch(/AM|PM/i);
    });

    it('renders the status dot', () => {
        const { container } = renderWithProvider();
        const dot = container.querySelector('.rounded-full');
        expect(dot).toBeInTheDocument();
    });

    it('does not render any buttons', () => {
        const { container } = renderWithProvider();
        const buttons = container.querySelectorAll('button');
        expect(buttons.length).toBe(0);
    });
});
