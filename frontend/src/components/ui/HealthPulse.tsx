export type ProjectHealth = 'on_track' | 'at_risk' | 'off_track';

export interface HealthPulseProps {
  health: ProjectHealth;
}

const HEALTH_META: Record<ProjectHealth, { glyph: string; label: string; style: string }> = {
  on_track: {
    glyph: '●',
    label: 'On track',
    style: 'bg-accent-50 text-accent-700 border-accent-100',
  },
  at_risk: {
    glyph: '◐',
    label: 'At risk',
    style: 'bg-brand-50 text-brand border-brand-100',
  },
  off_track: {
    glyph: '○',
    label: 'Off track',
    style: 'bg-neutral-50 text-neutral-900 border-neutral-200',
  },
};

export function HealthPulse({ health }: HealthPulseProps) {
  const meta = HEALTH_META[health];
  return (
    <span
      className={[
        'inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium',
        meta.style,
      ].join(' ')}
    >
      <span aria-hidden="true" className="text-[11px] leading-none">
        {meta.glyph}
      </span>
      <span>{meta.label}</span>
    </span>
  );
}
