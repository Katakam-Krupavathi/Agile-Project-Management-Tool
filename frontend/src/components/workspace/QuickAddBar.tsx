import { useState, type FormEvent } from 'react';
import { AlertCircle, Plus } from 'lucide-react';
import { Button } from '../ui';
import { parseQuickAdd, type ParsedQuickAdd } from '../../lib/quickAddParser';
import type { ProjectMember } from '../../lib/types';

export interface QuickAddBarProps {
  members: ProjectMember[];
  submitting?: boolean;
  onQuickAdd: (parsed: ParsedQuickAdd) => Promise<void>;
}

export function QuickAddBar({ members, submitting = false, onQuickAdd }: QuickAddBarProps) {
  const [input, setInput] = useState('');
  const [parseError, setParseError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const result = parseQuickAdd(input, members);
    if (!result.ok) {
      setParseError(result.error);
      return;
    }
    setParseError(null);
    await onQuickAdd(result.value);
    setInput('');
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded border border-neutral-200 bg-neutral-0 p-3 space-y-2"
      noValidate
    >
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            if (parseError) setParseError(null);
          }}
          placeholder="Quick-add story: Build auth flow @alex !high due:2026-12-01"
          aria-label="Quick-add story"
          className="min-w-[240px] flex-1 rounded border border-neutral-200 bg-neutral-0 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-500 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
        />
        <Button type="submit" size="md" loading={submitting}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          <span>Add story</span>
        </Button>
      </div>

      {parseError ? (
        <p role="alert" className="flex items-center gap-1.5 text-xs font-medium text-brand">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>{parseError}</span>
        </p>
      ) : (
        <p className="text-xs text-neutral-500">
          Syntax: <code className="font-mono text-neutral-900">title @assignee !priority due:YYYY-MM-DD</code>{' '}
          (priorities: low, medium, high, urgent; dates: YYYY-MM-DD, today, tomorrow).
        </p>
      )}
    </form>
  );
}
