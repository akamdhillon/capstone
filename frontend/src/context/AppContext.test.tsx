import { describe, it, expect } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { AppProvider, useApp } from './AppContext';

function TestConsumer() {
    const {
        currentView, setView,
        scores, overallScore, capturedImage, setScores,
        currentUser, setCurrentUser,
        triggerRecognition, setTriggerRecognition,
    } = useApp();

    return (
        <div>
            <span data-testid="view">{currentView}</span>
            <span data-testid="score">{overallScore ?? 'none'}</span>
            <span data-testid="image">{capturedImage ?? 'none'}</span>
            <span data-testid="skin">{scores?.skin ?? 'none'}</span>
            <span data-testid="user">{currentUser?.name ?? 'none'}</span>
            <span data-testid="trigger">{String(triggerRecognition)}</span>
            <button data-testid="set-view" onClick={() => setView('analysis')} />
            <button data-testid="set-scores" onClick={() => setScores(
                { skin: 80, posture: 70, eyes: 90, thermal: null },
                82,
                'img_data'
            )} />
            <button data-testid="set-user" onClick={() => setCurrentUser({ id: 'u1', name: 'Alice', created_at: '2024-01-01' })} />
            <button data-testid="set-trigger" onClick={() => setTriggerRecognition(true)} />
            <button data-testid="clear-trigger" onClick={() => setTriggerRecognition(false)} />
        </div>
    );
}

describe('AppContext', () => {
    it('renders children inside provider', () => {
        render(
            <AppProvider>
                <span>child content</span>
            </AppProvider>
        );
        expect(screen.getByText('child content')).toBeInTheDocument();
    });

    it('has correct default values', () => {
        render(<AppProvider><TestConsumer /></AppProvider>);
        expect(screen.getByTestId('view')).toHaveTextContent('idle');
        expect(screen.getByTestId('score')).toHaveTextContent('none');
        expect(screen.getByTestId('user')).toHaveTextContent('none');
        expect(screen.getByTestId('trigger')).toHaveTextContent('false');
    });

    it('setView updates currentView', () => {
        render(<AppProvider><TestConsumer /></AppProvider>);
        act(() => screen.getByTestId('set-view').click());
        expect(screen.getByTestId('view')).toHaveTextContent('analysis');
    });

    it('setScores updates scores, overallScore, and capturedImage', () => {
        render(<AppProvider><TestConsumer /></AppProvider>);
        act(() => screen.getByTestId('set-scores').click());
        expect(screen.getByTestId('score')).toHaveTextContent('82');
        expect(screen.getByTestId('image')).toHaveTextContent('img_data');
        expect(screen.getByTestId('skin')).toHaveTextContent('80');
    });

    it('setCurrentUser stores user object', () => {
        render(<AppProvider><TestConsumer /></AppProvider>);
        act(() => screen.getByTestId('set-user').click());
        expect(screen.getByTestId('user')).toHaveTextContent('Alice');
    });

    it('triggerRecognition state works correctly', () => {
        render(<AppProvider><TestConsumer /></AppProvider>);
        expect(screen.getByTestId('trigger')).toHaveTextContent('false');

        act(() => screen.getByTestId('set-trigger').click());
        expect(screen.getByTestId('trigger')).toHaveTextContent('true');

        act(() => screen.getByTestId('clear-trigger').click());
        expect(screen.getByTestId('trigger')).toHaveTextContent('false');
    });

    it('throws when useApp is used outside provider', () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        expect(() => render(<TestConsumer />)).toThrow('useApp must be used within an AppProvider');
        consoleSpy.mockRestore();
    });
});
