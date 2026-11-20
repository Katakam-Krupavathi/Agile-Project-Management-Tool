import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { ApiError, projectsApi, storiesApi, tasksApi } from '../lib/api';
import type { ProjectRole, ProjectTree, StoryPriority, StoryStatus, TaskStatus } from '../lib/types';
import { useToast, type ToastAction, type ToastTone } from '../components/ui';
import { projectTreeKey } from './useProjects';

export const projectMembersKey = (projectId: string) => ['projects', projectId, 'members'] as const;
export const projectActivityKey = (projectId: string) =>
  ['projects', projectId, 'activity'] as const;

function notifyWorkspaceError(
  err: unknown,
  fallback: string,
  projectId: string,
  queryClient: QueryClient,
  pushToast: (message: string, tone?: ToastTone, action?: ToastAction) => void,
) {
  if (err instanceof ApiError && err.status === 409) {
    pushToast(
      err.detail || 'This item was modified by another request. Reload to get the latest version.',
      'error',
      {
        label: 'Reload',
        onClick: () => {
          queryClient.invalidateQueries({ queryKey: projectTreeKey(projectId) });
          queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
        },
      },
    );
    return;
  }
  pushToast(err instanceof ApiError ? err.detail : fallback, 'error');
}

export function useProjectMembers(projectId: string | undefined) {
  return useQuery({
    queryKey: projectMembersKey(projectId ?? ''),
    queryFn: () => projectsApi.members(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useProjectActivity(projectId: string | undefined) {
  return useQuery({
    queryKey: projectActivityKey(projectId ?? ''),
    queryFn: () => projectsApi.activity(projectId!, 50),
    enabled: Boolean(projectId),
  });
}

export function useCreateStory(projectId: string) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: (payload: {
      title: string;
      description?: string | null;
      acceptance_criteria?: string | null;
      status?: StoryStatus;
      priority?: StoryPriority;
      story_points?: number | null;
      assignee_id?: string | null;
    }) => storiesApi.create(projectId, payload),
    onSuccess: (story) => {
      queryClient.invalidateQueries({ queryKey: projectTreeKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
      pushToast(`Created ${story.key}.`, 'success');
    },
    onError: (err) => {
      pushToast(err instanceof ApiError ? err.detail : 'Failed to create story.', 'error');
    },
  });
}

export function useUpdateStory(projectId: string) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: ({
      storyId,
      payload,
    }: {
      storyId: string;
      payload: {
        title?: string;
        description?: string | null;
        acceptance_criteria?: string | null;
        status?: StoryStatus;
        priority?: StoryPriority;
        story_points?: number | null;
        assignee_id?: string | null;
        version: number;
      };
    }) => storiesApi.update(storyId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectTreeKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
    },
    onError: (err) => {
      notifyWorkspaceError(err, 'Failed to update story.', projectId, queryClient, pushToast);
    },
  });
}

export function useMoveStory(projectId: string) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: ({
      storyId,
      payload,
    }: {
      storyId: string;
      payload: {
        status: StoryStatus;
        before_id?: string | null;
        after_id?: string | null;
        version: number;
      };
    }) => storiesApi.move(storyId, payload),
    onMutate: async ({ storyId, payload }) => {
      const key = projectTreeKey(projectId);
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<ProjectTree>(key);

      if (previous) {
        const movingNode = previous.stories.find((n) => n.story.id === storyId);
        if (movingNode) {
          const updatedNode = {
            ...movingNode,
            story: { ...movingNode.story, status: payload.status },
          };
          const remaining = previous.stories.filter((n) => n.story.id !== storyId);
          let insertIdx = remaining.length;
          if (payload.after_id) {
            const idx = remaining.findIndex((n) => n.story.id === payload.after_id);
            if (idx !== -1) insertIdx = idx;
          } else if (payload.before_id) {
            const idx = remaining.findIndex((n) => n.story.id === payload.before_id);
            if (idx !== -1) insertIdx = idx + 1;
          }
          const nextStories = [...remaining];
          nextStories.splice(insertIdx, 0, updatedNode);
          queryClient.setQueryData<ProjectTree>(key, {
            ...previous,
            stories: nextStories,
          });
        }
      }

      return { previous };
    },
    onError: (err, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(projectTreeKey(projectId), context.previous);
      }
      notifyWorkspaceError(err, 'Failed to move story.', projectId, queryClient, pushToast);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: projectTreeKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
    },
  });
}

export function useDeleteStory(projectId: string) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: (storyId: string) => storiesApi.remove(storyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectTreeKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
      pushToast('Story deleted.', 'info');
    },
    onError: (err) => {
      pushToast(err instanceof ApiError ? err.detail : 'Failed to delete story.', 'error');
    },
  });
}

export function useCreateTask(projectId: string) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: ({
      storyId,
      payload,
    }: {
      storyId: string;
      payload: {
        title: string;
        description?: string | null;
        status?: TaskStatus;
        assignee_id?: string | null;
        estimate_hours?: number | null;
        due_date?: string | null;
      };
    }) => tasksApi.create(storyId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectTreeKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
    },
    onError: (err) => {
      pushToast(err instanceof ApiError ? err.detail : 'Failed to create task.', 'error');
    },
  });
}

export function useUpdateTask(projectId: string) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: ({
      taskId,
      payload,
    }: {
      taskId: string;
      payload: {
        title?: string;
        description?: string | null;
        status?: TaskStatus;
        assignee_id?: string | null;
        estimate_hours?: number | null;
        due_date?: string | null;
        version: number;
      };
    }) => tasksApi.update(taskId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectTreeKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
    },
    onError: (err) => {
      notifyWorkspaceError(err, 'Failed to update task.', projectId, queryClient, pushToast);
    },
  });
}

export function useMoveTask(projectId: string) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: ({
      taskId,
      payload,
    }: {
      taskId: string;
      payload: {
        before_id?: string | null;
        after_id?: string | null;
        status?: TaskStatus | null;
        version: number;
      };
    }) => tasksApi.move(taskId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectTreeKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
    },
    onError: (err) => {
      notifyWorkspaceError(err, 'Failed to reorder task.', projectId, queryClient, pushToast);
    },
  });
}

export function useDeleteTask(projectId: string) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: (taskId: string) => tasksApi.remove(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectTreeKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
      pushToast('Task deleted.', 'info');
    },
    onError: (err) => {
      pushToast(err instanceof ApiError ? err.detail : 'Failed to delete task.', 'error');
    },
  });
}


export function useAddProjectMember(projectId: string) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: (payload: { email: string; role: ProjectRole }) =>
      projectsApi.addMember(projectId, payload),
    onSuccess: (member) => {
      queryClient.invalidateQueries({ queryKey: projectMembersKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
      pushToast(`Added ${member.name} as ${member.role}.`, 'success');
    },
    onError: (err) => {
      pushToast(err instanceof ApiError ? err.detail : 'Failed to add member.', 'error');
    },
  });
}

export function useUpdateProjectMemberRole(projectId: string) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: ProjectRole }) =>
      projectsApi.updateMemberRole(projectId, userId, role),
    onSuccess: (member) => {
      queryClient.invalidateQueries({ queryKey: projectMembersKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectTreeKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
      pushToast(`Updated ${member.name} to ${member.role}.`, 'success');
    },
    onError: (err) => {
      pushToast(err instanceof ApiError ? err.detail : 'Failed to update member role.', 'error');
    },
  });
}

export function useRemoveProjectMember(projectId: string) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: (userId: string) => projectsApi.removeMember(projectId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectMembersKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
      pushToast('Member removed from project.', 'info');
    },
    onError: (err) => {
      pushToast(err instanceof ApiError ? err.detail : 'Failed to remove member.', 'error');
    },
  });
}
