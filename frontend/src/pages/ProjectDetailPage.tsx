import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Kanban, ListTree } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { Badge, ErrorState, ProgressRail, Skeleton } from '../components/ui';
import { OutlineView } from '../components/workspace/OutlineView';
import { useCurrentUser, useLogout } from '../hooks/useAuth';
import { useProjects, useProjectTree } from '../hooks/useProjects';
import {
  useCreateTask,
  useProjectMembers,
  useUpdateStory,
  useUpdateTask,
} from '../hooks/useWorkspace';

export type WorkspaceViewMode = 'outline' | 'board';

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const { data: projectsPage } = useProjects(Boolean(user));
  const { data: tree, isLoading, isError, error, refetch } = useProjectTree(projectId);
  const { data: membersPage } = useProjectMembers(projectId);
  const updateStory = useUpdateStory(projectId ?? '');
  const createTask = useCreateTask(projectId ?? '');
  const updateTask = useUpdateTask(projectId ?? '');

  if (!user) return null;

  const projects = projectsPage?.items ?? [];
  const members = membersPage?.items ?? [];
  const canEdit = tree ? tree.project.role !== 'viewer' : false;
  const rawView = searchParams.get('view');
  const viewMode: WorkspaceViewMode = rawView === 'board' ? 'board' : 'outline';

  const setViewMode = (mode: WorkspaceViewMode) => {
    const next = new URLSearchParams(searchParams);
    next.set('view', mode);
    setSearchParams(next, { replace: true });
  };

  const handleLogout = async () => {
    await logout.mutateAsync();
    navigate('/login', { replace: true });
  };

  const viewToggle = (
    <div
      role="tablist"
      aria-label="Workspace view"
      className="inline-flex rounded border border-neutral-200 bg-neutral-50 p-0.5"
    >
      <button
        type="button"
        role="tab"
        aria-selected={viewMode === 'outline'}
        onClick={() => setViewMode('outline')}
        className={[
          'inline-flex items-center gap-1.5 rounded px-3 py-1 text-xs font-medium transition-colors',
          viewMode === 'outline'
            ? 'bg-brand text-neutral-0'
            : 'text-neutral-500 hover:text-neutral-900',
        ].join(' ')}
      >
        <ListTree className="h-3.5 w-3.5" aria-hidden="true" />
        <span>Outline</span>
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={viewMode === 'board'}
        onClick={() => setViewMode('board')}
        className={[
          'inline-flex items-center gap-1.5 rounded px-3 py-1 text-xs font-medium transition-colors',
          viewMode === 'board'
            ? 'bg-brand text-neutral-0'
            : 'text-neutral-500 hover:text-neutral-900',
        ].join(' ')}
      >
        <Kanban className="h-3.5 w-3.5" aria-hidden="true" />
        <span>Board</span>
      </button>
    </div>
  );

  return (
    <AppShell
      user={user}
      projects={projects}
      onLogout={handleLogout}
      loggingOut={logout.isPending}
      title={tree ? `${tree.project.key} · ${tree.project.name}` : 'Project'}
      health={tree?.rollup.health}
      viewToggle={viewToggle}
    >
      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : isError || !tree ? (
        <ErrorState
          title="Unable to load project"
          message={error instanceof Error ? error.message : 'Project not found.'}
          onRetry={() => refetch()}
        />
      ) : (
        <div className="space-y-5">
          <section className="flex flex-wrap items-center justify-between gap-4 rounded border border-neutral-200 bg-neutral-0 px-5 py-3.5">
            <div className="flex items-center gap-3">
              <Badge variant="brand" className="font-mono">
                {tree.project.key}
              </Badge>
              <Badge variant="outline">{tree.project.role}</Badge>
              <span className="text-xs text-neutral-500">
                {tree.rollup.done_stories}/{tree.rollup.total_stories} stories ·{' '}
                {tree.rollup.done_tasks}/{tree.rollup.total_tasks} tasks done
              </span>
            </div>
            <div className="w-48">
              <ProgressRail value={tree.rollup.progress_pct} />
            </div>
          </section>

          <OutlineView
            stories={tree.stories}
            members={members}
            canEdit={canEdit}
            onUpdateStory={(story, patch) =>
              updateStory.mutate({
                storyId: story.id,
                payload: { ...patch, version: story.version },
              })
            }
            onCreateTask={async (storyId, title) => {
              await createTask.mutateAsync({ storyId, payload: { title } });
            }}
            onUpdateTask={(task, patch) =>
              updateTask.mutate({
                taskId: task.id,
                payload: { ...patch, version: task.version },
              })
            }
          />
        </div>
      )}
    </AppShell>
  );
}
