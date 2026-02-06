import React from 'react';
import { GlassCard } from './ui/GlassCard';

interface MetricCardProps {
    label: string;
    score: number | null;
    icon: string;
    detail?: string;
    className?: string;
    disabled?: boolean;
}

export function MetricCard({ label, score, icon, detail, className = '', disabled = false }: MetricCardProps) {
    const getScoreColor = (score: number | null) => {
        if (score === null) return 'text-white/40';
        if (score >= 80) return 'text-green-400';
        if (score >= 60) return 'text-lime-400';
        if (score >= 40) return 'text-yellow-400';
        if (score >= 20) return 'text-orange-400';
        return 'text-red-400';
    };

    const getScoreLabel = (score: number | null) => {
        if (score === null) return 'N/A';
        if (score >= 80) return 'Excellent';
        if (score >= 60) return 'Good';
        if (score >= 40) return 'Fair';
        if (score >= 20) return 'Poor';
        return 'Needs Work';
    };

    return (
        <GlassCard className={`animate-fade-in ${className} ${disabled ? 'opacity-40 grayscale' : ''}`} subtle>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <span className="text-3xl">{icon}</span>
                    <div>
                        <h3 className="text-white/90 font-medium">{label}</h3>
                        {detail && (
                            <p className="text-white/50 text-sm mt-0.5">{detail}</p>
                        )}
                    </div>
                </div>
                <div className="text-right">
                    <div className={`text-3xl font-bold ${getScoreColor(score)}`}>
                        {score !== null ? Math.round(score) : '—'}
                    </div>
                    <div className={`text-xs ${getScoreColor(score)} opacity-80`}>
                        {getScoreLabel(score)}
                    </div>
                </div>
            </div>
        </GlassCard>
    );
}
