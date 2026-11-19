import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { CreateProjectModal } from '../components/projects/CreateProjectModal';
import { ProjectCard } from '../components/projects/ProjectCard';
import { Button, EmptyState, ErrorState, Skeleton } from '../components/ui';
import { useCurrentUser, useLogout } from '../hooks/useAuth';
import { useProjects } from '../hooks/useProjects';

export function ProjectsPage() {
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const { data: projectsPage, isLoading, isError, error, refetch } = useProjects(Boolean(user));
  const [createOpen, setCreateOpen] = useState(false);

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
      title="Projects"
      headerActions={
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          <span>New project</span>
        </Button>
      }
    >
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((item) => (
            <div
              key={item}
              className="space-y-3 rounded border border-neutral-200 bg-neutral-0 p-5"
            >
              <Skeleton className="h-5 w-24" />
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-2 w-full" />
            </div>
          ))}
        </div>
      ) : isError ? (
        <ErrorState
          title="Could not load projects"
          message={error instanceof Error ? error.message : 'Unexpected error'}
          onRetry={() => refetch()}
        />
      ) : projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          description="Create your first project to organize user stories and tasks for your team."
          action={
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              <span>New project</span>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}

      <CreateProjectModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </AppShell>
  );
}
