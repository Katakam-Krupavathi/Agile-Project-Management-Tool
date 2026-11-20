import type { StoryPriority, StoryStatus, Task, TaskStatus } from './types';

export const STORY_STATUS_LABELS: Record<StoryStatus, string> = {
  backlog: 'Backlog',
  in_progress: 'In Progress',
  in_review: 'In Review',
  done: 'Done',
};

export const STORY_STATUS_OPTIONS: { value: StoryStatus; label: string }[] = [
  { value: 'backlog', label: 'Backlog' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'in_review', label: 'In Review' },
  { value: 'done', label: 'Done' },
];

export const STORY_PRIORITY_LABELS: Record<StoryPriority, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  urgent: 'Urgent',
};

export const STORY_PRIORITY_OPTIONS: { value: StoryPriority; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
];

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  todo: 'To Do',
  doing: 'Doing',
  blocked: 'Blocked',
  done: 'Done',
};

export const TASK_STATUS_OPTIONS: { value: TaskStatus; label: string }[] = [
  { value: 'todo', label: 'To Do' },
  { value: 'doing', label: 'Doing' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'done', label: 'Done' },
];

export function parseUtcTimestamp(isoTimestamp: string): Date {
  const trimmed = isoTimestamp.trim();
  const hasTimezone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(trimmed);
  return new Date(hasTimezone ? trimmed : `${trimmed}Z`);
}

export function formatLocalDateKey(date: Date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function isTaskOverdue(
  task: Pick<Task, 'due_date' | 'status'>,
  now: Date = new Date(),
): boolean {
  if (!task.due_date || task.status === 'done') return false;
  const todayLocal = formatLocalDateKey(now);
  return task.due_date < todayLocal;
}
