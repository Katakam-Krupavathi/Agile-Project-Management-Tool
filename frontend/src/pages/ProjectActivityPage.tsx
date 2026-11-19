import { useInfiniteQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { buildProjectNav } from '../components/layout/projectNav';
import { Avatar, Badge, Button, EmptyState, ErrorState, Skeleton } from '../components/ui';
import { useCurrentUser, useLogout } from '../hooks/useAuth';
import { useProjects, useProjectTree } from '../hooks/useProjects';
import { projectsApi } from '../lib/api';
import { STORY_STATUS_LABELS, TASK_STATUS_LABELS } from '../lib/labels';
import type { ActivityLog, StoryStatus, TaskStatus } from '../lib/types';

function formatStatusLabel(value: unknown): string {
  if (typeof value !== 'string') return String(value ?? '');
  if (value in STORY_STATUS_LABELS) return STORY_STATUS_LABELS[value as StoryStatus];
  if (value in TASK_STATUS_LABELS) return TASK_STATUS_LABELS[value as TaskStatus];
  return value;
}

function formatActivityMessage(entry: ActivityLog): string {
  const actor = entry.actor_name ?? 'System';
  const details = entry.details ?? {};

  if (entry.action === 'story.moved') {
    const statusDiff = details.status as { to?: unknown } | undefined;
    if (statusDiff?.to) {
      return `${actor} moved story to ${formatStatusLabel(statusDiff.to)}`;
    }
    return `${actor} reordered a story`;
  }
  if (entry.action === 'story.created') {
    const key = typeof details.key === 'string' ? details.key : 'story';
    const title = typeof details.title === 'string' ? ` "${details.title}"` : '';
    return `${actor} created ${key}${title}`;
  }
  if (entry.action === 'story.updated') {
    const fields = Object.keys(details);
    return `${actor} updated story (${fields.join(', ') || 'details'})`;
  }
  if (entry.action === 'story.deleted') {
    const title = typeof details.title === 'string' ? ` "${details.title}"` : '';
    return `${actor} deleted story${title}`;
  }
  if (entry.action === 'task.created') {
    const title = typeof details.title === 'string' ? ` "${details.title}"` : '';
    return `${actor} created task${title}`;
  }
  if (entry.action === 'task.updated') {
    const statusDiff = details.status as { from?: unknown; to?: unknown } | undefined;
    if (statusDiff?.to) {
      return `${actor} changed task status to ${formatStatusLabel(statusDiff.to)}`;
    }
    const fields = Object.keys(details);
    return `${actor} updated task (${fields.join(', ') || 'details'})`;
  }
  if (entry.action === 'task.moved') {
    return `${actor} reordered a task`;
  }
  if (entry.action === 'task.deleted') {
    const title = typeof details.title === 'string' ? ` "${details.title}"` : '';
    return `${actor} deleted task${title}`;
  }
  if (entry.action === 'project.created') {
    return `${actor} created project ${typeof details.key === 'string' ? details.key : ''}`.trim();
  }
  if (entry.action === 'project_member.added') {
    return `${actor} added a member (${String(details.role ?? 'member')})`;
  }
  if (entry.action === 'project_member.removed') {
    return `${actor} removed a project member`;
  }
  return `${actor} performed ${entry.action}`;
}

export function ProjectActivityPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const { data: projectsPage } = useProjects(Boolean(user));
  const { data: tree } = useProjectTree(projectId);

  const activityQuery = useInfiniteQuery({
    queryKey: ['projects', projectId, 'activity-feed'],
    queryFn: ({ pageParam }) =>
      projectsApi.activity(projectId!, 20, pageParam as string | null),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.next_cursor : undefined),
    enabled: Boolean(projectId),
  });

  if (!user) return null;

  const projects = projectsPage?.items ?? [];
  const entries = activityQuery.data?.pages.flatMap((page) => page.items) ?? [];

  const handleLogout = async () => {
    await logout.mutateAsync();
    navigate('/login', { replace: true });
  };

  return (
    <AppShell
      user={user}
      projects={projects}
      projectNav={buildProjectNav(projectId)}
      onLogout={handleLogout}
      loggingOut={logout.isPending}
      title={tree ? `${tree.project.key} · Activity` : 'Project Activity'}
      health={tree?.rollup.health}
    >
      {activityQuery.isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : activityQuery.isError ? (
        <ErrorState
          title="Could not load activity"
          message={
            activityQuery.error instanceof Error
              ? activityQuery.error.message
              : 'Unexpected error'
          }
          onRetry={() => activityQuery.refetch()}
        />
      ) : entries.length === 0 ? (
        <EmptyState
          icon={<Activity className="h-5 w-5" aria-hidden="true" />}
          title="No activity yet"
          description="Project mutations, story moves, and task updates will appear here."
        />
      ) : (
        <div className="space-y-4">
          <ul className="divide-y divide-neutral-200 overflow-hidden rounded border border-neutral-200 bg-neutral-0">
            {entries.map((entry) => (
              <li key={entry.id} className="flex items-start justify-between gap-4 px-4 py-3.5">
                <div className="flex items-start gap-3">
                  <Avatar name={entry.actor_name ?? 'System'} size="sm" />
                  <div>
                    <p className="text-sm text-neutral-900">{formatActivityMessage(entry)}</p>
                    <p className="mt-0.5 text-xs text-neutral-500">
                      {new Date(entry.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
                <Badge variant="outline">{entry.entity_type.replace('_', ' ')}</Badge>
              </li>
            ))}
          </ul>

          {activityQuery.hasNextPage && (
            <div className="flex justify-center">
              <Button
                variant="secondary"
                size="sm"
                loading={activityQuery.isFetchingNextPage}
                onClick={() => activityQuery.fetchNextPage()}
              >
                Load more
              </Button>
            </div>
          )}
        </div>
      )}
    </AppShell>
  );
}
