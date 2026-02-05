import React, { useState, useEffect } from 'react';

interface ClockProps {
    className?: string;
    showDate?: boolean;
}

export function Clock({ className = '', showDate = false }: ClockProps) {
    const [time, setTime] = useState(new Date());

    useEffect(() => {
        const interval = setInterval(() => {
            setTime(new Date());
        }, 1000);

        return () => clearInterval(interval);
    }, []);

    const formatTime = (date: Date) => {
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: true,
        });
    };

    const formatDate = (date: Date) => {
        return date.toLocaleDateString('en-US', {
            weekday: 'long',
            month: 'long',
            day: 'numeric',
        });
    };

    return (
        <div className={`text-center ${className}`}>
            <div className="text-7xl font-light text-white/90 tracking-wide">
                {formatTime(time)}
            </div>
            {showDate && (
                <div className="text-xl text-white/50 mt-2 font-light">
                    {formatDate(time)}
                </div>
            )}
        </div>
    );
}
