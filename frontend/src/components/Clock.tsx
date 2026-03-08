import { useState, useEffect } from 'react';

interface ClockProps {
    className?: string;
    showDate?: boolean;
}

export function Clock({ className = '', showDate = false }: ClockProps) {
    const [time, setTime] = useState(new Date());

    useEffect(() => {
        const interval = setInterval(() => setTime(new Date()), 1000);
        return () => clearInterval(interval);
    }, []);

    const formatTime = (date: Date) =>
        date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: true,
        });

    const formatDate = (date: Date) =>
        date.toLocaleDateString('en-US', {
            weekday: 'long',
            month: 'long',
            day: 'numeric',
        });

    return (
        <div className={`text-center ${className}`}>
            <div className="text-7xl font-extralight text-white/85 tracking-wider tabular-nums">
                {formatTime(time)}
            </div>
            {showDate && (
                <div className="text-lg text-white/25 mt-3 font-light tracking-wide">
                    {formatDate(time)}
                </div>
            )}
        </div>
    );
}
