import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, projectsApi } from '../lib/api';
import { useToast } from '../components/ui';

export const PROJECTS_KEY = ['projects'] as const;
export const projectTreeKey = (projectId: string) => ['projects', projectId, 'tree'] as const;

export function useProjects(enabled = true) {
  return useQuery({
    queryKey: PROJECTS_KEY,
    queryFn: () => projectsApi.list(100),
    enabled,
  });
}

export function useProjectTree(projectId: string | undefined) {
  return useQuery({
    queryKey: projectTreeKey(projectId ?? ''),
    queryFn: () => projectsApi.tree(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: projectsApi.create,
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: PROJECTS_KEY });
      pushToast(`Project ${created.key} created.`, 'success');
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.detail : 'Failed to create project.';
      pushToast(msg, 'error');
    },
  });
}
