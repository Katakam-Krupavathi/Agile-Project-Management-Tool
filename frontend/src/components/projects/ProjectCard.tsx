import { Link } from 'react-router-dom';
import { Badge, HealthPulse, ProgressRail, Skeleton } from '../ui';
import { useProjectTree } from '../../hooks/useProjects';
import type { Project } from '../../lib/types';

export function ProjectCard({ project }: { project: Project }) {
  const { data: tree, isLoading } = useProjectTree(project.id);

  return (
    <Link
      to={`/projects/${project.id}`}
      className="group flex flex-col justify-between rounded border border-neutral-200 bg-neutral-0 p-5 transition-colors hover:border-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
    >
      <div>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge variant="brand" className="font-mono">
              {project.key}
            </Badge>
            <Badge variant="outline">{project.role}</Badge>
          </div>
          {isLoading ? (
            <Skeleton className="h-5 w-20" />
          ) : (
            tree && <HealthPulse health={tree.rollup.health} />
          )}
        </div>

        <h2 className="mt-3 text-base font-semibold text-neutral-900 group-hover:text-brand">
          {project.name}
        </h2>

        {project.description && (
          <p className="mt-1 line-clamp-2 text-sm text-neutral-500">{project.description}</p>
        )}
      </div>

      <div className="mt-5 space-y-2 border-t border-neutral-200 pt-3">
        {isLoading ? (
          <Skeleton className="h-3 w-full" />
        ) : tree ? (
          <>
            <ProgressRail value={tree.rollup.progress_pct} />
            <div className="flex items-center justify-between text-xs text-neutral-500">
              <span>
                {tree.rollup.total_stories}{' '}
                {tree.rollup.total_stories === 1 ? 'story' : 'stories'}
              </span>
              <span>
                {tree.rollup.done_tasks}/{tree.rollup.total_tasks} tasks done
              </span>
            </div>
          </>
        ) : (
          <p className="text-xs text-neutral-500">Open project</p>
        )}
      </div>
    </Link>
  );
}
