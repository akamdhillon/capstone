import React, { ReactNode } from 'react';

interface ButtonProps {
    children: ReactNode;
    onClick?: () => void;
    variant?: 'primary' | 'secondary';
    disabled?: boolean;
    className?: string;
    type?: 'button' | 'submit';
}

export function Button({
    children,
    onClick,
    variant = 'primary',
    disabled = false,
    className = '',
    type = 'button',
}: ButtonProps) {
    const baseClass = variant === 'primary' ? 'btn-primary' : 'btn-secondary';

    return (
        <button
            type={type}
            onClick={onClick}
            disabled={disabled}
            className={`${baseClass} ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}
        >
            {children}
        </button>
    );
}
