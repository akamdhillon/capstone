import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Clock } from './Clock';

describe('Clock', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date('2026-03-07T14:30:00'));
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('renders current time', () => {
        render(<Clock />);
        expect(screen.getByText(/02:30/i)).toBeInTheDocument();
    });

    it('shows date when showDate is true', () => {
        render(<Clock showDate />);
        expect(screen.getByText(/March/)).toBeInTheDocument();
        expect(screen.getByText(/Saturday/)).toBeInTheDocument();
    });

    it('hides date when showDate is false', () => {
        render(<Clock showDate={false} />);
        expect(screen.queryByText(/March/)).not.toBeInTheDocument();
    });

    it('hides date by default', () => {
        render(<Clock />);
        expect(screen.queryByText(/March/)).not.toBeInTheDocument();
    });
});
