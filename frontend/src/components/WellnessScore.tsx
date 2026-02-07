
import { CircularProgress } from './ui/CircularProgress';

interface WellnessScoreProps {
    score: number;
    className?: string;
    size?: number;
}

export function WellnessScore({ score, className = '', size = 240 }: WellnessScoreProps) {
    const getMessage = (score: number) => {
        if (score >= 80) return "Excellent! You're looking great today.";
        if (score >= 60) return "Good job! Keep up the healthy habits.";
        if (score >= 40) return "Some room for improvement.";
        return "Let's work on your wellness today.";
    };

    return (
        <div className={`flex flex-col items-center ${className}`}>
            <CircularProgress value={score} size={size} strokeWidth={14} />
            <p className="text-white/70 text-lg mt-6 text-center max-w-xs">
                {getMessage(score)}
            </p>
        </div>
    );
}
