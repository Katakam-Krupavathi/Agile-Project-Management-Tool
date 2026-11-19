import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { Badge, EmptyState, ErrorState, ProgressRail, Skeleton } from '../components/ui';
import { useCurrentUser, useLogout } from '../hooks/useAuth';
import { useProjects, useProjectTree } from '../hooks/useProjects';

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const { data: projectsPage } = useProjects(Boolean(user));
  const { data: tree, isLoading, isError, error, refetch } = useProjectTree(projectId);

  if (!user) return null;

  const projects = projectsPage?.items ?? [];

  const handleLogout = async () => {
    await logout.mutateAsync();
    navigate('/login', { replace: true });
  };

  return (
    <AppShell
      user={user}
      projects={projects}
      onLogout={handleLogout}
      loggingOut={logout.isPending}
      title={tree ? `${tree.project.key} · ${tree.project.name}` : 'Project'}
      health={tree?.rollup.health}
      headerActions={
        <Link
          to="/projects"
          className="inline-flex items-center gap-1.5 rounded border border-neutral-200 bg-neutral-0 px-3 py-1.5 text-xs font-medium text-neutral-900 hover:bg-neutral-50"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          <span>All projects</span>
        </Link>
      }
    >
      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : isError || !tree ? (
        <ErrorState
          title="Unable to load project"
          message={error instanceof Error ? error.message : 'Project not found.'}
          onRetry={() => refetch()}
        />
      ) : (
        <div className="space-y-6">
          <section className="rounded border border-neutral-200 bg-neutral-0 p-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <Badge variant="brand" className="font-mono">
                    {tree.project.key}
                  </Badge>
                  <Badge variant="outline">{tree.project.role}</Badge>
                </div>
                {tree.project.description && (
                  <p className="mt-2 text-sm text-neutral-500">{tree.project.description}</p>
                )}
              </div>
              <div className="w-full max-w-xs space-y-1.5">
                <p className="text-xs font-medium text-neutral-500">Overall progress</p>
                <ProgressRail value={tree.rollup.progress_pct} />
                <p className="text-xs text-neutral-500">
                  {tree.rollup.done_stories}/{tree.rollup.total_stories} stories ·{' '}
                  {tree.rollup.done_tasks}/{tree.rollup.total_tasks} tasks done
                </p>
              </div>
            </div>
          </section>

          {tree.stories.length === 0 ? (
            <EmptyState
              title="No stories yet"
              description="This project has no user stories yet."
            />
          ) : (
            <section className="space-y-2">
              {tree.stories.map((node) => (
                <div
                  key={node.story.id}
                  className="flex items-center justify-between gap-4 rounded border border-neutral-200 bg-neutral-0 px-4 py-3"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-brand">
                        {node.story.key}
                      </span>
                      <span className="truncate text-sm font-medium text-neutral-900">
                        {node.story.title}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="neutral">{node.story.status.replace('_', ' ')}</Badge>
                    <div className="w-28">
                      <ProgressRail value={node.rollup.progress_pct} />
                    </div>
                  </div>
                </div>
              ))}
            </section>
          )}
        </div>
      )}
    </AppShell>
  );
}
