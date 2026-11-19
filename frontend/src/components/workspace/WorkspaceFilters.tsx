import { Search, X } from 'lucide-react';
import { Button } from '../ui';
import { STORY_STATUS_OPTIONS } from '../../lib/labels';
import type { ProjectMember, StoryStatus } from '../../lib/types';

export interface WorkspaceFilterState {
  status: StoryStatus | 'all';
  assigneeId: string; // '' = all, '__unassigned__' = unassigned, or user_id
  query: string;
}

export interface WorkspaceFiltersProps {
  value: WorkspaceFilterState;
  members: ProjectMember[];
  onChange: (next: WorkspaceFilterState) => void;
}

export function WorkspaceFilters({ value, members, onChange }: WorkspaceFiltersProps) {
  const hasActiveFilter =
    value.status !== 'all' || value.assigneeId !== '' || value.query.trim() !== '';

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="relative min-w-[220px] flex-1">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-500"
          aria-hidden="true"
        />
        <input
          type="search"
          value={value.query}
          onChange={(e) => onChange({ ...value, query: e.target.value })}
          placeholder="Search stories and tasks..."
          aria-label="Search stories and tasks"
          className="w-full rounded border border-neutral-200 bg-neutral-0 py-1.5 pl-9 pr-3 text-sm text-neutral-900 placeholder:text-neutral-500 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
        />
      </div>

      <select
        aria-label="Filter by status"
        value={value.status}
        onChange={(e) =>
          onChange({ ...value, status: e.target.value as StoryStatus | 'all' })
        }
        className="rounded border border-neutral-200 bg-neutral-0 px-3 py-1.5 text-sm text-neutral-900 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
      >
        <option value="all">All statuses</option>
        {STORY_STATUS_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      <select
        aria-label="Filter by assignee"
        value={value.assigneeId}
        onChange={(e) => onChange({ ...value, assigneeId: e.target.value })}
        className="rounded border border-neutral-200 bg-neutral-0 px-3 py-1.5 text-sm text-neutral-900 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
      >
        <option value="">All assignees</option>
        <option value="__unassigned__">Unassigned</option>
        {members.map((m) => (
          <option key={m.user_id} value={m.user_id}>
            {m.name}
          </option>
        ))}
      </select>

      {hasActiveFilter && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onChange({ status: 'all', assigneeId: '', query: '' })}
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Clear</span>
        </Button>
      )}
    </div>
  );
}
