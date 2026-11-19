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

export function isTaskOverdue(task: Pick<Task, 'due_date' | 'status'>): boolean {
  if (!task.due_date || task.status === 'done') return false;
  const today = new Date().toISOString().slice(0, 10);
  return task.due_date < today;
}
