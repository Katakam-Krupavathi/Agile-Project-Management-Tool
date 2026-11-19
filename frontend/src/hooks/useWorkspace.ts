import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, projectsApi, storiesApi, tasksApi } from '../lib/api';
import type { StoryPriority, StoryStatus, TaskStatus } from '../lib/types';
import { useToast } from '../components/ui';
import { projectTreeKey } from './useProjects';

export const projectMembersKey = (projectId: string) => ['projects', projectId, 'members'] as const;
export const projectActivityKey = (projectId: string) =>
  ['projects', projectId, 'activity'] as const;

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
      pushToast(err instanceof ApiError ? err.detail : 'Failed to update story.', 'error');
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
        version?: number;
      };
    }) => storiesApi.move(storyId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectTreeKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
    },
    onError: (err) => {
      pushToast(err instanceof ApiError ? err.detail : 'Failed to move story.', 'error');
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
      pushToast(err instanceof ApiError ? err.detail : 'Failed to update task.', 'error');
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
        version?: number;
      };
    }) => tasksApi.move(taskId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectTreeKey(projectId) });
      queryClient.invalidateQueries({ queryKey: projectActivityKey(projectId) });
    },
    onError: (err) => {
      pushToast(err instanceof ApiError ? err.detail : 'Failed to reorder task.', 'error');
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
