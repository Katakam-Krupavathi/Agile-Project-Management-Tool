export type ProjectRole = 'owner' | 'member' | 'viewer';
export type StoryStatus = 'backlog' | 'in_progress' | 'in_review' | 'done';
export type StoryPriority = 'low' | 'medium' | 'high' | 'urgent';
export type TaskStatus = 'todo' | 'doing' | 'blocked' | 'done';
export type ProjectHealth = 'on_track' | 'at_risk' | 'off_track';
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'dead';

export interface ValidationErrorItem {
  field: string;
  message: string;
  type: string;
}

export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
  code: string;
  errors?: ValidationErrorItem[];
}

export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface User {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthSession {
  user: User;
  csrf_token: string;
}

export interface Project {
  id: string;
  key: string;
  name: string;
  description: string | null;
  next_story_number: number;
  created_by: string;
  version: number;
  role: ProjectRole;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface ProjectMember {
  id: string;
  project_id: string;
  user_id: string;
  email: string;
  name: string;
  role: ProjectRole;
  created_at: string;
}

export interface Story {
  id: string;
  project_id: string;
  number: number;
  key: string;
  title: string;
  description: string | null;
  acceptance_criteria: string | null;
  status: StoryStatus;
  priority: StoryPriority;
  story_points: number | null;
  assignee_id: string | null;
  position: number;
  version: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface Task {
  id: string;
  story_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  assignee_id: string | null;
  estimate_hours: number | null;
  due_date: string | null;
  position: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface StoryRollup {
  total_tasks: number;
  done_tasks: number;
  blocked_tasks: number;
  overdue_tasks: number;
  progress_pct: number;
  is_blocked: boolean;
  suggested_status: StoryStatus | null;
}

export interface ProjectRollup {
  health: ProjectHealth;
  total_stories: number;
  done_stories: number;
  stalled_stories: number;
  total_tasks: number;
  done_tasks: number;
  blocked_tasks: number;
  overdue_tasks: number;
  progress_pct: number;
}

export interface StoryTreeNode {
  story: Story;
  rollup: StoryRollup;
  tasks: Task[];
}

export interface ProjectTree {
  project: Project;
  rollup: ProjectRollup;
  stories: StoryTreeNode[];
}

export interface ActivityLog {
  id: string;
  project_id: string;
  actor_id: string | null;
  actor_name: string | null;
  entity_type: string;
  entity_id: string;
  action: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface Notification {
  id: string;
  user_id: string;
  project_id: string | null;
  type: string;
  title: string;
  body: string | null;
  entity_type: string | null;
  entity_id: string | null;
  read_at: string | null;
  created_at: string;
}

export interface NotificationPage extends CursorPage<Notification> {
  unread_count: number;
}

export interface Job {
  id: string;
  job_type: string;
  status: JobStatus;
  attempts: number;
  max_attempts: number;
  run_at: string;
  last_error: string | null;
  result: Record<string, unknown> | null;
  project_id: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface ReportEnqueueResponse {
  job_id: string;
  status: JobStatus;
}

export interface ReportSummary {
  id: string;
  project_id: string;
  job_id: string | null;
  title: string;
  created_by: string | null;
  created_at: string;
}
