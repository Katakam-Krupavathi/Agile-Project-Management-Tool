import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Kanban, ListTree } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { Badge, EmptyState, ErrorState, ProgressRail, Skeleton } from '../components/ui';
import { useCurrentUser, useLogout } from '../hooks/useAuth';
import { useProjects, useProjectTree } from '../hooks/useProjects';

export type WorkspaceViewMode = 'outline' | 'board';

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const { data: projectsPage } = useProjects(Boolean(user));
  const { data: tree, isLoading, isError, error, refetch } = useProjectTree(projectId);

  if (!user) return null;

  const projects = projectsPage?.items ?? [];
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

          {tree.stories.length === 0 ? (
            <EmptyState
              title="No stories yet"
              description="Add user stories to start tracking work in Outline or Board view."
            />
          ) : (
            <div className="space-y-2">
              {tree.stories.map((node) => (
                <div
                  key={node.story.id}
                  className="flex items-center justify-between gap-4 rounded border border-neutral-200 bg-neutral-0 px-4 py-3"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-brand">
                      {node.story.key}
                    </span>
                    <span className="truncate text-sm font-medium text-neutral-900">
                      {node.story.title}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="neutral">{node.story.status.replace('_', ' ')}</Badge>
                    <div className="w-28">
                      <ProgressRail value={node.rollup.progress_pct} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </AppShell>
  );
}
