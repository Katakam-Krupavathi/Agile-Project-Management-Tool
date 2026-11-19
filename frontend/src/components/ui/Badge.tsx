import type { ReactNode } from 'react';

type BadgeVariant = 'brand' | 'accent' | 'neutral' | 'outline';

export interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  brand: 'bg-brand-50 text-brand border-brand-100',
  accent: 'bg-accent-50 text-accent-700 border-accent-100',
  neutral: 'bg-neutral-50 text-neutral-900 border-neutral-200',
  outline: 'bg-neutral-0 text-neutral-500 border-neutral-200',
};

export function Badge({ variant = 'neutral', children, className = '' }: BadgeProps) {
  return (
    <span
      className={[
        'inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium',
        VARIANT_CLASSES[variant],
        className,
      ].join(' ')}
    >
      {children}
    </span>
  );
}
