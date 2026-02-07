import { useEffect, useState } from 'react';

interface CircularProgressProps {
    value: number;
    size?: number;
    strokeWidth?: number;
    className?: string;
}

export function CircularProgress({
    value,
    size = 200,
    strokeWidth = 12,
    className = '',
}: CircularProgressProps) {
    const [animatedValue, setAnimatedValue] = useState(0);

    // Animate the value on change
    useEffect(() => {
        const duration = 1000;
        const startTime = Date.now();
        const startValue = animatedValue;

        const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = startValue + (value - startValue) * eased;
            setAnimatedValue(current);

            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };

        requestAnimationFrame(animate);
    }, [value]);

    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (animatedValue / 100) * circumference;

    // Color based on score
    const getColor = (score: number) => {
        if (score >= 80) return '#4ade80'; // Green
        if (score >= 60) return '#a3e635'; // Lime
        if (score >= 40) return '#facc15'; // Yellow
        if (score >= 20) return '#fb923c'; // Orange
        return '#f87171'; // Red
    };

    const color = getColor(animatedValue);
    const glowClass = animatedValue >= 60 ? 'glow-success' : animatedValue >= 40 ? 'glow-warning' : 'glow-danger';

    return (
        <div className={`relative ${className}`} style={{ width: size, height: size }}>
            <svg
                className={`transform -rotate-90 ${glowClass}`}
                width={size}
                height={size}
            >
                {/* Background circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    stroke="rgba(255, 255, 255, 0.1)"
                    strokeWidth={strokeWidth}
                    fill="none"
                />
                {/* Progress circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    stroke={color}
                    strokeWidth={strokeWidth}
                    fill="none"
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    style={{ transition: 'stroke 0.3s ease' }}
                />
            </svg>
            {/* Center content */}
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span
                    className="text-5xl font-bold"
                    style={{ color }}
                >
                    {Math.round(animatedValue)}
                </span>
                <span className="text-sm text-white/60 mt-1">Wellness Score</span>
            </div>
        </div>
    );
}
