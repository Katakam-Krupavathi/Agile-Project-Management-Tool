import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Kanban, ListTree } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { buildProjectNav } from '../components/layout/projectNav';
import { Badge, ErrorState, ProgressRail, Skeleton } from '../components/ui';
import { BoardView } from '../components/workspace/BoardView';
import { OutlineView } from '../components/workspace/OutlineView';
import { QuickAddBar } from '../components/workspace/QuickAddBar';
import { StoryFocusDrawer } from '../components/workspace/StoryFocusDrawer';
import {
  WorkspaceFilters,
  type WorkspaceFilterState,
} from '../components/workspace/WorkspaceFilters';
import { useCurrentUser, useLogout } from '../hooks/useAuth';
import { canEditProjectItems } from '../lib/permissions';
import { useProjects, useProjectTree } from '../hooks/useProjects';
import {
  useCreateStory,
  useCreateTask,
  useDeleteStory,
  useDeleteTask,
  useMoveStory,
  useMoveTask,
  useProjectActivity,
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
  const { data: activityPage } = useProjectActivity(projectId);
  const createStory = useCreateStory(projectId ?? '');
  const updateStory = useUpdateStory(projectId ?? '');
  const moveStory = useMoveStory(projectId ?? '');
  const deleteStory = useDeleteStory(projectId ?? '');
  const createTask = useCreateTask(projectId ?? '');
  const updateTask = useUpdateTask(projectId ?? '');
  const moveTask = useMoveTask(projectId ?? '');
  const deleteTask = useDeleteTask(projectId ?? '');
  const [selectedStoryId, setSelectedStoryId] = useState<string | null>(null);
  const [filters, setFilters] = useState<WorkspaceFilterState>({
    status: 'all',
    assigneeId: '',
    query: '',
  });

  useEffect(() => {
    if (!tree) return;
    const storyParam = searchParams.get('story');
    const taskParam = searchParams.get('task');
    if (storyParam && tree.stories.some((n) => n.story.id === storyParam)) {
      setSelectedStoryId(storyParam);
    } else if (taskParam) {
      const parent = tree.stories.find((n) => n.tasks.some((t) => t.id === taskParam));
      if (parent) {
        setSelectedStoryId(parent.story.id);
      }
    }
  }, [tree, searchParams]);

  const filteredStories = useMemo(() => {
    if (!tree) return [];
    const q = filters.query.trim().toLowerCase();
    return tree.stories.filter((node) => {
      if (filters.status !== 'all' && node.story.status !== filters.status) {
        return false;
      }
      if (filters.assigneeId === '__unassigned__' && node.story.assignee_id !== null) {
        return false;
      }
      if (
        filters.assigneeId &&
        filters.assigneeId !== '__unassigned__' &&
        node.story.assignee_id !== filters.assigneeId
      ) {
        return false;
      }
      if (q) {
        const inStory =
          node.story.key.toLowerCase().includes(q) ||
          node.story.title.toLowerCase().includes(q) ||
          (node.story.description ?? '').toLowerCase().includes(q);
        const inTasks = node.tasks.some((t) => t.title.toLowerCase().includes(q));
        if (!inStory && !inTasks) return false;
      }
      return true;
    });
  }, [tree, filters]);

  if (!user) return null;

  const projects = projectsPage?.items ?? [];
  const members = membersPage?.items ?? [];
  const activity = activityPage?.items ?? [];
  const canEdit = canEditProjectItems(tree?.project.role);
  const selectedStoryNode =
    selectedStoryId && tree
      ? tree.stories.find((n) => n.story.id === selectedStoryId) ?? null
      : null;
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
      projectNav={buildProjectNav(projectId, tree?.project.role)}
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

          {canEdit && viewMode === 'outline' && (
            <QuickAddBar
              members={members}
              submitting={createStory.isPending}
              onQuickAdd={async (parsed) => {
                const story = await createStory.mutateAsync({
                  title: parsed.title,
                  assignee_id: parsed.assigneeId,
                  priority: parsed.priority,
                });
                if (parsed.dueDate) {
                  await createTask.mutateAsync({
                    storyId: story.id,
                    payload: {
                      title: parsed.title,
                      assignee_id: parsed.assigneeId,
                      due_date: parsed.dueDate,
                    },
                  });
                }
              }}
            />
          )}

          <WorkspaceFilters value={filters} members={members} onChange={setFilters} />

          {viewMode === 'outline' ? (
            <OutlineView
              stories={filteredStories}
              members={members}
              canEdit={canEdit}
              onSelectStory={setSelectedStoryId}
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
          ) : (
            <BoardView
              stories={filteredStories}
              members={members}
              canEdit={canEdit}
              onSelectStory={setSelectedStoryId}
              onMoveStory={(story, target) =>
                moveStory.mutate({
                  storyId: story.id,
                  payload: { ...target, version: story.version },
                })
              }
            />
          )}

          <StoryFocusDrawer
            node={selectedStoryNode}
            members={members}
            activity={activity}
            canEdit={canEdit}
            onClose={() => setSelectedStoryId(null)}
            onUpdateStory={async (story, patch) => {
              await updateStory.mutateAsync({
                storyId: story.id,
                payload: { ...patch, version: story.version },
              });
            }}
            onDeleteStory={async (storyId) => {
              await deleteStory.mutateAsync(storyId);
            }}
            onCreateTask={async (storyId, payload) => {
              await createTask.mutateAsync({ storyId, payload });
            }}
            onUpdateTask={async (task, patch) => {
              await updateTask.mutateAsync({
                taskId: task.id,
                payload: { ...patch, version: task.version },
              });
            }}
            onMoveTask={async (task, target) => {
              await moveTask.mutateAsync({
                taskId: task.id,
                payload: { ...target, version: task.version },
              });
            }}
            onDeleteTask={async (taskId) => {
              await deleteTask.mutateAsync(taskId);
            }}
          />
        </div>
      )}
    </AppShell>
  );
}
