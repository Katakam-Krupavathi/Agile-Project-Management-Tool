export interface ProgressRailProps {
  value: number;
  showLabel?: boolean;
  className?: string;
}

export function ProgressRail({ value, showLabel = true, className = '' }: ProgressRailProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className={['flex items-center gap-2', className].join(' ')}>
      <div
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-2 flex-1 overflow-hidden rounded bg-neutral-200"
      >
        <div
          className="h-full rounded bg-accent transition-all duration-200"
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && (
        <span className="w-10 text-right text-xs font-medium tabular-nums text-neutral-500">
          {clamped}%
        </span>
      )}
    </div>
  );
}
