export interface AvatarProps {
  name: string;
  size?: 'sm' | 'md';
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function Avatar({ name, size = 'md' }: AvatarProps) {
  const sizeClass = size === 'sm' ? 'h-6 w-6 text-[11px]' : 'h-8 w-8 text-xs';
  return (
    <span
      title={name}
      aria-label={name}
      className={[
        'inline-flex shrink-0 items-center justify-center rounded-full',
        'bg-brand-50 font-semibold text-brand border border-brand-100',
        sizeClass,
      ].join(' ')}
    >
      {getInitials(name)}
    </span>
  );
}
