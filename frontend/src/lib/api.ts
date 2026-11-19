import type {
  ActivityLog,
  AuthSession,
  CursorPage,
  Job,
  Notification,
  NotificationPage,
  ProblemDetail,
  Project,
  ProjectMember,
  ProjectRole,
  ProjectTree,
  ReportEnqueueResponse,
  ReportSummary,
  Story,
  StoryPriority,
  StoryStatus,
  Task,
  TaskStatus,
  User,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const CSRF_COOKIE_NAME = 'agile_pm_csrf';
const MUTATING_METHODS = new Set(['POST', 'PATCH', 'PUT', 'DELETE']);

let memoryCsrfToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export function setCsrfToken(token: string | null): void {
  memoryCsrfToken = token;
}

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  const parts = document.cookie.split(';');
  for (const part of parts) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }
  return null;
}

function getCsrfToken(): string | null {
  return readCookie(CSRF_COOKIE_NAME) ?? memoryCsrfToken;
}

export class ApiError extends Error {
  status: number;
  code: string;
  detail: string;
  problem?: ProblemDetail;

  constructor(status: number, detail: string, code = 'API_ERROR', problem?: ProblemDetail) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.problem = problem;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  skipUnauthorizedRedirect?: boolean;
}

async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase();
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...options.headers,
  };

  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  if (MUTATING_METHODS.has(method)) {
    const csrf = getCsrfToken();
    if (csrf) {
      headers['X-CSRF-Token'] = csrf;
    }
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: 'include',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('content-type') ?? '';
  const isJson =
    contentType.includes('application/json') || contentType.includes('application/problem+json');

  if (!response.ok) {
    let problem: ProblemDetail | undefined;
    let detail = response.statusText || 'Request failed';
    let code = `HTTP_${response.status}`;

    if (isJson) {
      try {
        problem = (await response.json()) as ProblemDetail;
        detail = problem.detail || detail;
        code = problem.code || code;
      } catch {
        // ignore JSON parse failure on error body
      }
    }

    if (response.status === 401 && !options.skipUnauthorizedRedirect && unauthorizedHandler) {
      unauthorizedHandler();
    }

    throw new ApiError(response.status, detail, code, problem);
  }

  if (!isJson) {
    return (await response.text()) as unknown as T;
  }

  return (await response.json()) as T;
}

export const authApi = {
  register: (payload: { email: string; name: string; password: string }) =>
    apiRequest<User>('/auth/register', {
      method: 'POST',
      body: payload,
      skipUnauthorizedRedirect: true,
    }),

  login: async (payload: { email: string; password: string }) => {
    const session = await apiRequest<AuthSession>('/auth/login', {
      method: 'POST',
      body: payload,
      skipUnauthorizedRedirect: true,
    });
    setCsrfToken(session.csrf_token);
    return session;
  },

  logout: async () => {
    await apiRequest<void>('/auth/logout', { method: 'POST' });
    setCsrfToken(null);
  },

  me: () =>
    apiRequest<User>('/auth/me', {
      skipUnauthorizedRedirect: true,
    }),
};

export const projectsApi = {
  list: (limit = 50) => apiRequest<CursorPage<Project>>(`/projects?limit=${limit}`),

  create: (payload: { key: string; name: string; description?: string | null }) =>
    apiRequest<Project>('/projects', { method: 'POST', body: payload }),

  get: (projectId: string) => apiRequest<Project>(`/projects/${projectId}`),

  update: (
    projectId: string,
    payload: { name?: string; description?: string | null; version: number },
  ) => apiRequest<Project>(`/projects/${projectId}`, { method: 'PATCH', body: payload }),

  archive: (projectId: string) =>
    apiRequest<void>(`/projects/${projectId}`, { method: 'DELETE' }),

  tree: (projectId: string) => apiRequest<ProjectTree>(`/projects/${projectId}/tree`),

  members: (projectId: string) =>
    apiRequest<CursorPage<ProjectMember>>(`/projects/${projectId}/members?limit=100`),

  addMember: (projectId: string, payload: { email: string; role: ProjectRole }) =>
    apiRequest<ProjectMember>(`/projects/${projectId}/members`, {
      method: 'POST',
      body: payload,
    }),

  updateMemberRole: (projectId: string, userId: string, role: ProjectRole) =>
    apiRequest<ProjectMember>(`/projects/${projectId}/members/${userId}`, {
      method: 'PATCH',
      body: { role },
    }),

  removeMember: (projectId: string, userId: string) =>
    apiRequest<void>(`/projects/${projectId}/members/${userId}`, { method: 'DELETE' }),

  activity: (projectId: string, limit = 30, cursor?: string | null) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) params.set('cursor', cursor);
    return apiRequest<CursorPage<ActivityLog>>(`/projects/${projectId}/activity?${params}`);
  },
};

export const storiesApi = {
  create: (
    projectId: string,
    payload: {
      title: string;
      description?: string | null;
      acceptance_criteria?: string | null;
      status?: StoryStatus;
      priority?: StoryPriority;
      story_points?: number | null;
      assignee_id?: string | null;
    },
  ) =>
    apiRequest<Story>(`/projects/${projectId}/stories`, {
      method: 'POST',
      body: payload,
    }),

  update: (
    storyId: string,
    payload: {
      title?: string;
      description?: string | null;
      acceptance_criteria?: string | null;
      status?: StoryStatus;
      priority?: StoryPriority;
      story_points?: number | null;
      assignee_id?: string | null;
      version: number;
    },
  ) => apiRequest<Story>(`/stories/${storyId}`, { method: 'PATCH', body: payload }),

  move: (
    storyId: string,
    payload: {
      status: StoryStatus;
      before_id?: string | null;
      after_id?: string | null;
      version?: number;
    },
  ) => apiRequest<Story>(`/stories/${storyId}/move`, { method: 'POST', body: payload }),

  remove: (storyId: string) => apiRequest<void>(`/stories/${storyId}`, { method: 'DELETE' }),
};

export const tasksApi = {
  create: (
    storyId: string,
    payload: {
      title: string;
      description?: string | null;
      status?: TaskStatus;
      assignee_id?: string | null;
      estimate_hours?: number | null;
      due_date?: string | null;
    },
  ) => apiRequest<Task>(`/stories/${storyId}/tasks`, { method: 'POST', body: payload }),

  update: (
    taskId: string,
    payload: {
      title?: string;
      description?: string | null;
      status?: TaskStatus;
      assignee_id?: string | null;
      estimate_hours?: number | null;
      due_date?: string | null;
      version: number;
    },
  ) => apiRequest<Task>(`/tasks/${taskId}`, { method: 'PATCH', body: payload }),

  move: (
    taskId: string,
    payload: {
      before_id?: string | null;
      after_id?: string | null;
      status?: TaskStatus | null;
      version?: number;
    },
  ) => apiRequest<Task>(`/tasks/${taskId}/move`, { method: 'POST', body: payload }),

  remove: (taskId: string) => apiRequest<void>(`/tasks/${taskId}`, { method: 'DELETE' }),
};

export const notificationsApi = {
  list: (limit = 30) => apiRequest<NotificationPage>(`/notifications?limit=${limit}`),

  markRead: (notificationId: string) =>
    apiRequest<Notification>(`/notifications/${notificationId}/read`, { method: 'PATCH' }),

  markAllRead: () =>
    apiRequest<{ updated: number }>('/notifications/read-all', { method: 'POST' }),
};

export const reportsApi = {
  enqueue: (projectId: string, idempotencyKey: string) =>
    apiRequest<ReportEnqueueResponse>(`/projects/${projectId}/reports`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
    }),

  list: (projectId: string) =>
    apiRequest<CursorPage<ReportSummary>>(`/projects/${projectId}/reports?limit=20`),

  downloadUrl: (reportId: string) => `${API_BASE}/reports/${reportId}`,
};

export const jobsApi = {
  get: (jobId: string) => apiRequest<Job>(`/jobs/${jobId}`),

  retry: (jobId: string) => apiRequest<Job>(`/jobs/${jobId}/retry`, { method: 'POST' }),
};
