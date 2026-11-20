import { useEffect, useState, type FormEvent } from 'react';
import {
  AlertOctagon,
  ArrowDown,
  ArrowUp,
  Calendar,
  Clock,
  Plus,
  Trash2,
} from 'lucide-react';
import { Avatar, Badge, Button, Drawer, Input, ProgressRail, Select } from '../ui';
import {
  isTaskOverdue,
  parseUtcTimestamp,
  STORY_PRIORITY_LABELS,
  STORY_PRIORITY_OPTIONS,
  STORY_STATUS_LABELS,
  STORY_STATUS_OPTIONS,
  TASK_STATUS_LABELS,
  TASK_STATUS_OPTIONS,
} from '../../lib/labels';
import type {
  ActivityLog,
  ProjectMember,
  Story,
  StoryPriority,
  StoryStatus,
  StoryTreeNode,
  Task,
  TaskStatus,
} from '../../lib/types';

export interface StoryFocusDrawerProps {
  node: StoryTreeNode | null;
  members: ProjectMember[];
  activity: ActivityLog[];
  canEdit: boolean;
  onClose: () => void;
  onUpdateStory: (
    story: Story,
    patch: {
      title?: string;
      description?: string | null;
      acceptance_criteria?: string | null;
      status?: StoryStatus;
      priority?: StoryPriority;
      story_points?: number | null;
      assignee_id?: string | null;
    },
  ) => Promise<void> | void;
  onDeleteStory: (storyId: string) => Promise<void> | void;
  onCreateTask: (
    storyId: string,
    payload: {
      title: string;
      assignee_id?: string | null;
      due_date?: string | null;
      estimate_hours?: number | null;
    },
  ) => Promise<void> | void;
  onUpdateTask: (
    task: Task,
    patch: {
      title?: string;
      status?: TaskStatus;
      assignee_id?: string | null;
      due_date?: string | null;
      estimate_hours?: number | null;
    },
  ) => Promise<void> | void;
  onMoveTask: (
    task: Task,
    target: { before_id: string | null; after_id: string | null },
  ) => Promise<void> | void;
  onDeleteTask: (taskId: string) => Promise<void> | void;
}

export function StoryFocusDrawer({
  node,
  members,
  activity,
  canEdit,
  onClose,
  onUpdateStory,
  onDeleteStory,
  onCreateTask,
  onUpdateTask,
  onMoveTask,
  onDeleteTask,
}: StoryFocusDrawerProps) {
  const story = node?.story ?? null;

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [acceptanceCriteria, setAcceptanceCriteria] = useState('');
  const [status, setStatus] = useState<StoryStatus>('backlog');
  const [priority, setPriority] = useState<StoryPriority>('medium');
  const [storyPoints, setStoryPoints] = useState('');
  const [assigneeId, setAssigneeId] = useState('');
  const [savingStory, setSavingStory] = useState(false);
  const [confirmDeleteStory, setConfirmDeleteStory] = useState(false);

  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskAssignee, setNewTaskAssignee] = useState('');
  const [newTaskDueDate, setNewTaskDueDate] = useState('');
  const [newTaskHours, setNewTaskHours] = useState('');
  const [confirmDeleteTaskId, setConfirmDeleteTaskId] = useState<string | null>(null);

  useEffect(() => {
    if (!story) return;
    setTitle(story.title);
    setDescription(story.description ?? '');
    setAcceptanceCriteria(story.acceptance_criteria ?? '');
    setStatus(story.status);
    setPriority(story.priority);
    setStoryPoints(story.story_points !== null ? String(story.story_points) : '');
    setAssigneeId(story.assignee_id ?? '');
    setConfirmDeleteStory(false);
    setConfirmDeleteTaskId(null);
  }, [story]);

  if (!node || !story) {
    return <Drawer open={false} title="" onClose={onClose}>{null}</Drawer>;
  }

  const memberById = new Map(members.map((m) => [m.user_id, m]));
  const storyAssignee = story.assignee_id ? memberById.get(story.assignee_id) : undefined;
  const taskIds = new Set(node.tasks.map((t) => t.id));
  const relevantActivity = activity.filter(
    (entry) => entry.entity_id === story.id || taskIds.has(entry.entity_id),
  );

  const handleSaveStory = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    setSavingStory(true);
    try {
      await onUpdateStory(story, {
        title: title.trim(),
        description: description.trim() ? description.trim() : null,
        acceptance_criteria: acceptanceCriteria.trim() ? acceptanceCriteria.trim() : null,
        status,
        priority,
        story_points: storyPoints.trim() ? Number(storyPoints) : null,
        assignee_id: assigneeId || null,
      });
    } finally {
      setSavingStory(false);
    }
  };

  const handleAddTask = async (event: FormEvent) => {
    event.preventDefault();
    if (!newTaskTitle.trim()) return;
    await onCreateTask(story.id, {
      title: newTaskTitle.trim(),
      assignee_id: newTaskAssignee || null,
      due_date: newTaskDueDate || null,
      estimate_hours: newTaskHours.trim() ? Number(newTaskHours) : null,
    });
    setNewTaskTitle('');
    setNewTaskAssignee('');
    setNewTaskDueDate('');
    setNewTaskHours('');
  };

  const handleReorderTask = (index: number, direction: 'up' | 'down') => {
    const task = node.tasks[index];
    if (!task) return;
    if (direction === 'up' && index > 0) {
      const targetBefore = index - 2 >= 0 ? node.tasks[index - 2].id : null;
      const targetAfter = node.tasks[index - 1].id;
      onMoveTask(task, { before_id: targetBefore, after_id: targetAfter });
    } else if (direction === 'down' && index < node.tasks.length - 1) {
      const targetBefore = node.tasks[index + 1].id;
      const targetAfter = index + 2 < node.tasks.length ? node.tasks[index + 2].id : null;
      onMoveTask(task, { before_id: targetBefore, after_id: targetAfter });
    }
  };

  return (
    <Drawer open={true} title={`${story.key} · Story details`} onClose={onClose}>
      <div className="space-y-6">
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge variant="brand" className="font-mono">
                {story.key}
              </Badge>
              <Badge variant="outline">v{story.version}</Badge>
              {node.rollup.is_blocked && (
                <Badge variant="brand">
                  <AlertOctagon className="h-3 w-3" aria-hidden="true" />
                  <span>Blocked</span>
                </Badge>
              )}
            </div>
            {canEdit &&
              (confirmDeleteStory ? (
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={async () => {
                      await onDeleteStory(story.id);
                      onClose();
                    }}
                  >
                    Confirm delete
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setConfirmDeleteStory(false)}
                  >
                    Cancel
                  </Button>
                </div>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setConfirmDeleteStory(true)}
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Delete story</span>
                </Button>
              ))}
          </div>

          {canEdit ? (
            <form onSubmit={handleSaveStory} className="space-y-4">
              <Input
                label="Title"
                name="story-title"
                required
                maxLength={200}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />

              <div className="grid grid-cols-2 gap-3">
                <Select
                  label="Status"
                  name="story-status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value as StoryStatus)}
                  options={STORY_STATUS_OPTIONS}
                />
                <Select
                  label="Priority"
                  name="story-priority"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as StoryPriority)}
                  options={STORY_PRIORITY_OPTIONS}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Select
                  label="Assignee"
                  name="story-assignee"
                  value={assigneeId}
                  onChange={(e) => setAssigneeId(e.target.value)}
                  options={[
                    { value: '', label: 'Unassigned' },
                    ...members.map((m) => ({ value: m.user_id, label: m.name })),
                  ]}
                />
                <Input
                  label="Story points"
                  name="story-points"
                  type="number"
                  min={0}
                  max={100}
                  value={storyPoints}
                  onChange={(e) => setStoryPoints(e.target.value)}
                  placeholder="0–100"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="story-description" className="block text-sm font-medium text-neutral-900">
                  Description
                </label>
                <textarea
                  id="story-description"
                  rows={3}
                  maxLength={10000}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="block w-full rounded border border-neutral-200 bg-neutral-0 px-3 py-2 text-sm text-neutral-900 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="story-ac" className="block text-sm font-medium text-neutral-900">
                  Acceptance criteria
                </label>
                <textarea
                  id="story-ac"
                  rows={3}
                  maxLength={10000}
                  value={acceptanceCriteria}
                  onChange={(e) => setAcceptanceCriteria(e.target.value)}
                  className="block w-full rounded border border-neutral-200 bg-neutral-0 px-3 py-2 text-sm text-neutral-900 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
                />
              </div>

              <div className="flex justify-end">
                <Button type="submit" size="sm" loading={savingStory}>
                  Save changes
                </Button>
              </div>
            </form>
          ) : (
            <div className="space-y-3 rounded border border-neutral-200 bg-neutral-50 p-4">
              <h3 className="text-base font-semibold text-neutral-900">{story.title}</h3>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant={story.status === 'done' ? 'accent' : 'neutral'}>
                  {STORY_STATUS_LABELS[story.status]}
                </Badge>
                <Badge variant="outline">{STORY_PRIORITY_LABELS[story.priority]}</Badge>
                {story.story_points !== null && (
                  <Badge variant="outline">{story.story_points} pts</Badge>
                )}
                {storyAssignee && (
                  <span className="inline-flex items-center gap-1.5 text-neutral-900">
                    <Avatar name={storyAssignee.name} size="sm" />
                    <span>{storyAssignee.name}</span>
                  </span>
                )}
              </div>
              {story.description && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Description
                  </p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-neutral-900">
                    {story.description}
                  </p>
                </div>
              )}
              {story.acceptance_criteria && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Acceptance criteria
                  </p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-neutral-900">
                    {story.acceptance_criteria}
                  </p>
                </div>
              )}
            </div>
          )}
        </section>

        <section className="space-y-3 border-t border-neutral-200 pt-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-neutral-900">
              Tasks ({node.rollup.done_tasks}/{node.rollup.total_tasks})
            </h3>
            <div className="w-36">
              <ProgressRail value={node.rollup.progress_pct} />
            </div>
          </div>

          {node.tasks.length === 0 ? (
            <p className="text-xs text-neutral-500">No tasks yet.</p>
          ) : (
            <ul className="space-y-2">
              {node.tasks.map((task, idx) => {
                const overdue = isTaskOverdue(task);
                const taskAssignee = task.assignee_id
                  ? memberById.get(task.assignee_id)
                  : undefined;
                return (
                  <li
                    key={task.id}
                    className="space-y-2 rounded border border-neutral-200 bg-neutral-50 p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className={[
                          'text-sm font-medium',
                          task.status === 'done'
                            ? 'text-neutral-500 line-through'
                            : 'text-neutral-900',
                        ].join(' ')}
                      >
                        {task.title}
                      </span>

                      {canEdit && (
                        <div className="flex items-center gap-1">
                          {idx > 0 && (
                            <button
                              type="button"
                              aria-label={`Move ${task.title} up`}
                              onClick={() => handleReorderTask(idx, 'up')}
                              className="rounded p-1 text-neutral-500 hover:bg-neutral-0 hover:text-neutral-900"
                            >
                              <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                          )}
                          {idx < node.tasks.length - 1 && (
                            <button
                              type="button"
                              aria-label={`Move ${task.title} down`}
                              onClick={() => handleReorderTask(idx, 'down')}
                              className="rounded p-1 text-neutral-500 hover:bg-neutral-0 hover:text-neutral-900"
                            >
                              <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                          )}
                          {confirmDeleteTaskId === task.id ? (
                            <div className="flex items-center gap-1">
                              <Button
                                size="sm"
                                variant="primary"
                                onClick={async () => {
                                  await onDeleteTask(task.id);
                                  setConfirmDeleteTaskId(null);
                                }}
                              >
                                Delete
                              </Button>
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => setConfirmDeleteTaskId(null)}
                              >
                                Cancel
                              </Button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              aria-label={`Delete ${task.title}`}
                              onClick={() => setConfirmDeleteTaskId(task.id)}
                              className="rounded p-1 text-neutral-500 hover:bg-neutral-0 hover:text-brand"
                            >
                              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {canEdit ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <select
                          aria-label={`Drawer status for ${task.title}`}
                          value={task.status}
                          onChange={(e) =>
                            onUpdateTask(task, { status: e.target.value as TaskStatus })
                          }
                          className="rounded border border-neutral-200 bg-neutral-0 px-2 py-1 text-xs text-neutral-900"
                        >
                          {TASK_STATUS_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>

                        <select
                          aria-label={`Drawer assignee for ${task.title}`}
                          value={task.assignee_id ?? ''}
                          onChange={(e) =>
                            onUpdateTask(task, {
                              assignee_id: e.target.value ? e.target.value : null,
                            })
                          }
                          className="rounded border border-neutral-200 bg-neutral-0 px-2 py-1 text-xs text-neutral-900"
                        >
                          <option value="">Unassigned</option>
                          {members.map((m) => (
                            <option key={m.user_id} value={m.user_id}>
                              {m.name}
                            </option>
                          ))}
                        </select>

                        <input
                          type="date"
                          aria-label={`Drawer due date for ${task.title}`}
                          value={task.due_date ?? ''}
                          onChange={(e) =>
                            onUpdateTask(task, {
                              due_date: e.target.value ? e.target.value : null,
                            })
                          }
                          className="rounded border border-neutral-200 bg-neutral-0 px-2 py-1 text-xs text-neutral-900"
                        />

                        {overdue && (
                          <Badge variant="brand">
                            <Clock className="h-3 w-3" aria-hidden="true" />
                            <span>Overdue</span>
                          </Badge>
                        )}
                      </div>
                    ) : (
                      <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
                        <Badge variant={task.status === 'done' ? 'accent' : 'neutral'}>
                          {TASK_STATUS_LABELS[task.status]}
                        </Badge>
                        {task.estimate_hours !== null && <span>{task.estimate_hours}h</span>}
                        {task.due_date && (
                          <span className="inline-flex items-center gap-1">
                            <Calendar className="h-3 w-3" aria-hidden="true" />
                            <span>{task.due_date}</span>
                          </span>
                        )}
                        {taskAssignee && <span>{taskAssignee.name}</span>}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}

          {canEdit && (
            <form
              onSubmit={handleAddTask}
              className="space-y-2 rounded border border-neutral-200 bg-neutral-0 p-3"
            >
              <p className="text-xs font-medium text-neutral-900">Add task</p>
              <input
                type="text"
                required
                maxLength={200}
                value={newTaskTitle}
                onChange={(e) => setNewTaskTitle(e.target.value)}
                placeholder="Task title"
                className="w-full rounded border border-neutral-200 px-2.5 py-1.5 text-xs text-neutral-900 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
              />
              <div className="grid grid-cols-3 gap-2">
                <select
                  aria-label="New task assignee"
                  value={newTaskAssignee}
                  onChange={(e) => setNewTaskAssignee(e.target.value)}
                  className="rounded border border-neutral-200 px-2 py-1 text-xs text-neutral-900"
                >
                  <option value="">Unassigned</option>
                  {members.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.name}
                    </option>
                  ))}
                </select>
                <input
                  type="date"
                  aria-label="New task due date"
                  value={newTaskDueDate}
                  onChange={(e) => setNewTaskDueDate(e.target.value)}
                  className="rounded border border-neutral-200 px-2 py-1 text-xs text-neutral-900"
                />
                <input
                  type="number"
                  min={0}
                  max={1000}
                  step="0.5"
                  aria-label="New task estimate hours"
                  value={newTaskHours}
                  onChange={(e) => setNewTaskHours(e.target.value)}
                  placeholder="Est. hrs"
                  className="rounded border border-neutral-200 px-2 py-1 text-xs text-neutral-900"
                />
              </div>
              <div className="flex justify-end">
                <Button type="submit" size="sm" variant="secondary">
                  <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Add task</span>
                </Button>
              </div>
            </form>
          )}
        </section>

        <section className="space-y-2.5 border-t border-neutral-200 pt-5">
          <h3 className="text-sm font-semibold text-neutral-900">Activity timeline</h3>
          {relevantActivity.length === 0 ? (
            <p className="text-xs text-neutral-500">No recorded activity for this story.</p>
          ) : (
            <ul className="space-y-2">
              {relevantActivity.map((entry) => (
                <li
                  key={entry.id}
                  className="rounded border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-neutral-900">
                      {entry.actor_name ?? 'System'} ·{' '}
                      <code className="font-mono text-brand">{entry.action}</code>
                    </span>
                    <span className="text-neutral-500">
                      {parseUtcTimestamp(entry.created_at).toLocaleString()}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Drawer>
  );
}
