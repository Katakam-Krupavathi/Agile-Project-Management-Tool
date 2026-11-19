import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, jobsApi, reportsApi } from '../lib/api';
import { useToast } from '../components/ui';

export const projectReportsKey = (projectId: string) => ['projects', projectId, 'reports'] as const;
export const jobStatusKey = (jobId: string) => ['jobs', jobId] as const;

export function useProjectReports(projectId: string | undefined) {
  return useQuery({
    queryKey: projectReportsKey(projectId ?? ''),
    queryFn: () => reportsApi.list(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useEnqueueReport(projectId: string) {
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: () => {
      const key =
        typeof crypto !== 'undefined' && 'randomUUID' in crypto
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      return reportsApi.enqueue(projectId, key);
    },
    onSuccess: () => {
      pushToast('Report generation queued.', 'info');
    },
    onError: (err) => {
      pushToast(err instanceof ApiError ? err.detail : 'Failed to request report.', 'error');
    },
  });
}

export function useJobStatus(jobId: string | null) {
  return useQuery({
    queryKey: jobStatusKey(jobId ?? ''),
    queryFn: () => jobsApi.get(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || status === 'queued' || status === 'running') {
        return 1500;
      }
      return false;
    },
  });
}

export function useRetryJob() {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: (jobId: string) => jobsApi.retry(jobId),
    onSuccess: (job) => {
      queryClient.setQueryData(jobStatusKey(job.id), job);
      pushToast('Dead job re-queued for retry.', 'info');
    },
    onError: (err) => {
      pushToast(err instanceof ApiError ? err.detail : 'Failed to retry job.', 'error');
    },
  });
}
