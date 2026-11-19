import type { ReactNode } from 'react';
import { FolderOpen } from 'lucide-react';

export interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: ReactNode;
}

export function EmptyState({ title, description, action, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded border border-dashed border-neutral-200 bg-neutral-0 px-6 py-12 text-center">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded bg-brand-50 text-brand">
        {icon ?? <FolderOpen className="h-5 w-5" aria-hidden="true" />}
      </div>
      <h3 className="text-sm font-semibold text-neutral-900">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-neutral-500">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
