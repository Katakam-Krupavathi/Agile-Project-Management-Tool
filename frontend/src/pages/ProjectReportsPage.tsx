import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { Download, FileText } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { buildProjectNav } from '../components/layout/projectNav';
import { JobStatusCard } from '../components/reports/JobStatusCard';
import { Button, EmptyState, ErrorState, Skeleton } from '../components/ui';
import { useCurrentUser, useLogout } from '../hooks/useAuth';
import { useProjects, useProjectTree } from '../hooks/useProjects';
import {
  projectReportsKey,
  useEnqueueReport,
  useJobStatus,
  useProjectReports,
  useRetryJob,
} from '../hooks/useReports';
import { reportsApi } from '../lib/api';
import { canEditProjectItems, canManageProject } from '../lib/permissions';

export function ProjectReportsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const { data: projectsPage } = useProjects(Boolean(user));
  const { data: tree } = useProjectTree(projectId);
  const reportsQuery = useProjectReports(projectId);
  const enqueueReport = useEnqueueReport(projectId ?? '');
  const retryJob = useRetryJob();

  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const jobQuery = useJobStatus(activeJobId);

  useEffect(() => {
    if (jobQuery.data?.status === 'succeeded' && projectId) {
      queryClient.invalidateQueries({ queryKey: projectReportsKey(projectId) });
    }
  }, [jobQuery.data?.status, projectId, queryClient]);

  if (!user) return null;

  const projects = projectsPage?.items ?? [];
  const canGenerate = canEditProjectItems(tree?.project.role);
  const isOwner = canManageProject(tree?.project.role);
  const reports = reportsQuery.data?.items ?? [];

  const handleLogout = async () => {
    await logout.mutateAsync();
    navigate('/login', { replace: true });
  };

  const handleGenerate = async () => {
    const res = await enqueueReport.mutateAsync();
    setActiveJobId(res.job_id);
  };

  return (
    <AppShell
      user={user}
      projects={projects}
      projectNav={buildProjectNav(projectId, tree?.project.role)}
      onLogout={handleLogout}
      loggingOut={logout.isPending}
      title={tree ? `${tree.project.key} · Reports` : 'Project Reports'}
      health={tree?.rollup.health}
      headerActions={
        canGenerate ? (
          <Button size="sm" loading={enqueueReport.isPending} onClick={handleGenerate}>
            <FileText className="h-4 w-4" aria-hidden="true" />
            <span>Generate report</span>
          </Button>
        ) : undefined
      }
    >
      <div className="space-y-5">
        {jobQuery.data && (
          <JobStatusCard
            job={jobQuery.data}
            isOwner={isOwner}
            retrying={retryJob.isPending}
            onRetry={(jobId) => retryJob.mutate(jobId)}
          />
        )}

        {reportsQuery.isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : reportsQuery.isError ? (
          <ErrorState
            title="Could not load reports"
            message={
              reportsQuery.error instanceof Error
                ? reportsQuery.error.message
                : 'Unexpected error'
            }
            onRetry={() => reportsQuery.refetch()}
          />
        ) : reports.length === 0 ? (
          <EmptyState
            icon={<FileText className="h-5 w-5" aria-hidden="true" />}
            title="No reports generated yet"
            description="Generate a Markdown status report summarizing story progress, blocked items, overdue tasks, and recent activity."
            action={
              canGenerate ? (
                <Button loading={enqueueReport.isPending} onClick={handleGenerate}>
                  <FileText className="h-4 w-4" aria-hidden="true" />
                  <span>Generate report</span>
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ul className="divide-y divide-neutral-200 overflow-hidden rounded border border-neutral-200 bg-neutral-0">
            {reports.map((report) => (
              <li
                key={report.id}
                className="flex flex-wrap items-center justify-between gap-4 px-4 py-3.5"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded bg-brand-50 text-brand">
                    <FileText className="h-4 w-4" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-neutral-900">{report.title}</p>
                    <p className="text-xs text-neutral-500">
                      Generated {new Date(report.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
                <a
                  href={reportsApi.downloadUrl(report.id)}
                  download
                  className="inline-flex h-8 items-center gap-1.5 rounded border border-neutral-200 bg-neutral-0 px-3 text-xs font-medium text-neutral-900 hover:bg-neutral-50"
                >
                  <Download className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Download</span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  );
}
