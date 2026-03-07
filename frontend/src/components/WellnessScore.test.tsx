import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WellnessScore } from './WellnessScore';

describe('WellnessScore', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('renders the score value', () => {
        render(<WellnessScore score={85} />);
        expect(screen.getByText('Wellness Score')).toBeInTheDocument();
    });

    it('shows excellent message for score >= 80', () => {
        render(<WellnessScore score={90} />);
        expect(screen.getByText("Excellent! You're looking great today.")).toBeInTheDocument();
    });

    it('shows good message for score 60-79', () => {
        render(<WellnessScore score={65} />);
        expect(screen.getByText('Good job! Keep up the healthy habits.')).toBeInTheDocument();
    });

    it('shows improvement message for score 40-59', () => {
        render(<WellnessScore score={45} />);
        expect(screen.getByText('Some room for improvement.')).toBeInTheDocument();
    });

    it('shows low score message for score < 40', () => {
        render(<WellnessScore score={20} />);
        expect(screen.getByText("Let's work on your wellness today.")).toBeInTheDocument();
    });
});
