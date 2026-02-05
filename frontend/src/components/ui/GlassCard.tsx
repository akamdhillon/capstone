import React, { ReactNode } from 'react';

interface GlassCardProps {
    children: ReactNode;
    className?: string;
    subtle?: boolean;
}

export function GlassCard({ children, className = '', subtle = false }: GlassCardProps) {
    const baseClass = subtle ? 'glass-subtle' : 'glass';

    return (
        <div className={`${baseClass} p-6 ${className}`}>
            {children}
        </div>
    );
}
