import { useState, type FormEvent } from 'react';
import {
  AlertOctagon,
  ArrowRight,
  Calendar,
  ChevronDown,
  ChevronRight,
  Clock,
  Pencil,
  Plus,
} from 'lucide-react';
import { Avatar, Badge, Button, EmptyState, ProgressRail } from '../ui';
import {
  isTaskOverdue,
  STORY_PRIORITY_LABELS,
  STORY_STATUS_LABELS,
  STORY_STATUS_OPTIONS,
  TASK_STATUS_LABELS,
  TASK_STATUS_OPTIONS,
} from '../../lib/labels';
import type {
  ProjectMember,
  Story,
  StoryStatus,
  StoryTreeNode,
  Task,
  TaskStatus,
} from '../../lib/types';

export interface OutlineViewProps {
  stories: StoryTreeNode[];
  members: ProjectMember[];
  canEdit: boolean;
  onSelectStory?: (storyId: string) => void;
  onUpdateStory: (
    story: Story,
    patch: { title?: string; status?: StoryStatus; assignee_id?: string | null },
  ) => void;
  onCreateTask: (storyId: string, title: string) => Promise<void> | void;
  onUpdateTask: (
    task: Task,
    patch: {
      title?: string;
      status?: TaskStatus;
      assignee_id?: string | null;
      due_date?: string | null;
    },
  ) => void;
}

function InlineTitle({
  value,
  canEdit,
  onSave,
  onClickView,
  strike = false,
}: {
  value: string;
  canEdit: boolean;
  onSave: (nextTitle: string) => void;
  onClickView?: () => void;
  strike?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const commit = () => {
    const trimmed = draft.trim();
    setEditing(false);
    if (trimmed && trimmed !== value) {
      onSave(trimmed);
    } else {
      setDraft(value);
    }
  };

  if (editing && canEdit) {
    return (
      <input
        type="text"
        autoFocus
        maxLength={200}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit();
          if (e.key === 'Escape') {
            setDraft(value);
            setEditing(false);
          }
        }}
        aria-label="Edit title"
        className="w-full min-w-[160px] rounded border border-brand bg-neutral-0 px-2 py-0.5 text-sm text-neutral-900 focus:outline-none focus:ring-2 focus:ring-brand"
      />
    );
  }

  return (
    <div className="group/title flex min-w-0 flex-1 items-center gap-1.5">
      {onClickView ? (
        <button
          type="button"
          onClick={onClickView}
          className={[
            'truncate text-left text-sm font-medium hover:text-brand',
            strike ? 'text-neutral-500 line-through' : 'text-neutral-900',
          ].join(' ')}
        >
          {value}
        </button>
      ) : (
        <span
          className={[
            'truncate text-sm',
            strike ? 'text-neutral-500 line-through' : 'text-neutral-900',
          ].join(' ')}
        >
          {value}
        </span>
      )}
      {canEdit && (
        <button
          type="button"
          onClick={() => {
            setDraft(value);
            setEditing(true);
          }}
          aria-label={`Edit title: ${value}`}
          className="rounded p-1 text-neutral-500 opacity-0 transition-opacity hover:bg-neutral-50 hover:text-brand group-hover/title:opacity-100 focus:opacity-100"
        >
          <Pencil className="h-3 w-3" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

export function OutlineView({
  stories,
  members,
  canEdit,
  onSelectStory,
  onUpdateStory,
  onCreateTask,
  onUpdateTask,
}: OutlineViewProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [newTaskTitles, setNewTaskTitles] = useState<Record<string, string>>({});
  const memberById = new Map(members.map((m) => [m.user_id, m]));

  const toggleExpand = (storyId: string) => {
    setExpanded((prev) => ({ ...prev, [storyId]: !prev[storyId] }));
  };

  const handleAddTask = async (event: FormEvent, storyId: string) => {
    event.preventDefault();
    const title = (newTaskTitles[storyId] ?? '').trim();
    if (!title) return;
    setNewTaskTitles((prev) => ({ ...prev, [storyId]: '' }));
    await onCreateTask(storyId, title);
  };

  if (stories.length === 0) {
    return (
      <EmptyState
        title="No matching stories"
        description="Create a story or adjust your filters to view work items."
      />
    );
  }

  return (
    <div className="space-y-2">
      {stories.map((node) => {
        const { story, rollup, tasks } = node;
        const isOpen = Boolean(expanded[story.id]);
        const storyAssignee = story.assignee_id ? memberById.get(story.assignee_id) : undefined;

        return (
          <div
            key={story.id}
            className="overflow-hidden rounded border border-neutral-200 bg-neutral-0"
          >
            <div className="flex flex-wrap items-center gap-3 px-4 py-3">
              <button
                type="button"
                onClick={() => toggleExpand(story.id)}
                aria-expanded={isOpen}
                aria-label={isOpen ? `Collapse ${story.key} tasks` : `Expand ${story.key} tasks`}
                className="rounded p-1 text-neutral-500 hover:bg-neutral-50 hover:text-neutral-900"
              >
                {isOpen ? (
                  <ChevronDown className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <ChevronRight className="h-4 w-4" aria-hidden="true" />
                )}
              </button>

              <span className="w-16 shrink-0 font-mono text-xs font-semibold text-brand">
                {story.key}
              </span>

              <InlineTitle
                value={story.title}
                canEdit={canEdit}
                onClickView={onSelectStory ? () => onSelectStory(story.id) : undefined}
                onSave={(title) => onUpdateStory(story, { title })}
              />

              <div className="flex flex-wrap items-center gap-2">
                {rollup.is_blocked && (
                  <Badge variant="brand">
                    <AlertOctagon className="h-3 w-3" aria-hidden="true" />
                    <span>Blocked</span>
                  </Badge>
                )}

                {canEdit && rollup.suggested_status && (
                  <button
                    type="button"
                    onClick={() =>
                      onUpdateStory(story, { status: rollup.suggested_status ?? undefined })
                    }
                    className="inline-flex items-center gap-1 rounded border border-accent-200 bg-accent-50 px-2 py-0.5 text-xs font-medium text-accent-700 hover:bg-accent-100"
                  >
                    <ArrowRight className="h-3 w-3" aria-hidden="true" />
                    <span>Move to {STORY_STATUS_LABELS[rollup.suggested_status]}</span>
                  </button>
                )}

                {canEdit ? (
                  <select
                    aria-label={`Status for ${story.key}`}
                    value={story.status}
                    onChange={(e) =>
                      onUpdateStory(story, { status: e.target.value as StoryStatus })
                    }
                    className="rounded border border-neutral-200 bg-neutral-0 px-2 py-1 text-xs font-medium text-neutral-900 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                  >
                    {STORY_STATUS_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Badge variant={story.status === 'done' ? 'accent' : 'neutral'}>
                    {STORY_STATUS_LABELS[story.status]}
                  </Badge>
                )}

                <Badge variant={story.priority === 'urgent' ? 'brand' : 'outline'}>
                  {STORY_PRIORITY_LABELS[story.priority]}
                </Badge>

                {canEdit ? (
                  <select
                    aria-label={`Assignee for ${story.key}`}
                    value={story.assignee_id ?? ''}
                    onChange={(e) =>
                      onUpdateStory(story, {
                        assignee_id: e.target.value ? e.target.value : null,
                      })
                    }
                    className="max-w-[130px] rounded border border-neutral-200 bg-neutral-0 px-2 py-1 text-xs text-neutral-900 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                  >
                    <option value="">Unassigned</option>
                    {members.map((m) => (
                      <option key={m.user_id} value={m.user_id}>
                        {m.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  storyAssignee && <Avatar name={storyAssignee.name} size="sm" />
                )}

                <div className="w-28">
                  <ProgressRail value={rollup.progress_pct} />
                </div>

                <span className="w-16 text-right text-xs tabular-nums text-neutral-500">
                  {rollup.done_tasks}/{rollup.total_tasks} tasks
                </span>
              </div>
            </div>

            {isOpen && (
              <div className="border-t border-neutral-200 bg-neutral-50 px-6 py-3 space-y-2.5">
                {tasks.length === 0 ? (
                  <p className="text-xs text-neutral-500">No tasks under this story yet.</p>
                ) : (
                  <ul className="space-y-2">
                    {tasks.map((task) => {
                      const taskAssignee = task.assignee_id
                        ? memberById.get(task.assignee_id)
                        : undefined;
                      const overdue = isTaskOverdue(task);
                      return (
                        <li
                          key={task.id}
                          className="flex flex-wrap items-center justify-between gap-3 rounded border border-neutral-200 bg-neutral-0 px-3 py-2 text-sm"
                        >
                          <div className="flex min-w-0 flex-1 items-center gap-2.5">
                            {canEdit ? (
                              <select
                                aria-label={`Status for task ${task.title}`}
                                value={task.status}
                                onChange={(e) =>
                                  onUpdateTask(task, { status: e.target.value as TaskStatus })
                                }
                                className="rounded border border-neutral-200 bg-neutral-0 px-2 py-1 text-xs font-medium text-neutral-900 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                              >
                                {TASK_STATUS_OPTIONS.map((opt) => (
                                  <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <Badge
                                variant={
                                  task.status === 'done'
                                    ? 'accent'
                                    : task.status === 'blocked'
                                      ? 'brand'
                                      : 'neutral'
                                }
                              >
                                {task.status === 'blocked' && (
                                  <AlertOctagon className="h-3 w-3" aria-hidden="true" />
                                )}
                                <span>{TASK_STATUS_LABELS[task.status]}</span>
                              </Badge>
                            )}

                            <InlineTitle
                              value={task.title}
                              canEdit={canEdit}
                              strike={task.status === 'done'}
                              onSave={(title) => onUpdateTask(task, { title })}
                            />
                          </div>

                          <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
                            {overdue && (
                              <Badge variant="brand">
                                <Clock className="h-3 w-3" aria-hidden="true" />
                                <span>Overdue</span>
                              </Badge>
                            )}

                            {canEdit ? (
                              <input
                                type="date"
                                aria-label={`Due date for ${task.title}`}
                                value={task.due_date ?? ''}
                                onChange={(e) =>
                                  onUpdateTask(task, {
                                    due_date: e.target.value ? e.target.value : null,
                                  })
                                }
                                className="rounded border border-neutral-200 bg-neutral-0 px-2 py-1 text-xs text-neutral-900 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                              />
                            ) : (
                              task.due_date && (
                                <span className="inline-flex items-center gap-1">
                                  <Calendar className="h-3.5 w-3.5" aria-hidden="true" />
                                  <span>{task.due_date}</span>
                                </span>
                              )
                            )}

                            {canEdit ? (
                              <select
                                aria-label={`Assignee for ${task.title}`}
                                value={task.assignee_id ?? ''}
                                onChange={(e) =>
                                  onUpdateTask(task, {
                                    assignee_id: e.target.value ? e.target.value : null,
                                  })
                                }
                                className="max-w-[120px] rounded border border-neutral-200 bg-neutral-0 px-2 py-1 text-xs text-neutral-900 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                              >
                                <option value="">Unassigned</option>
                                {members.map((m) => (
                                  <option key={m.user_id} value={m.user_id}>
                                    {m.name}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              taskAssignee && <Avatar name={taskAssignee.name} size="sm" />
                            )}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}

                {canEdit && (
                  <form
                    onSubmit={(e) => handleAddTask(e, story.id)}
                    className="flex items-center gap-2 pt-1"
                  >
                    <input
                      type="text"
                      maxLength={200}
                      value={newTaskTitles[story.id] ?? ''}
                      onChange={(e) =>
                        setNewTaskTitles((prev) => ({ ...prev, [story.id]: e.target.value }))
                      }
                      placeholder="Add a task..."
                      aria-label={`New task for ${story.key}`}
                      className="flex-1 rounded border border-neutral-200 bg-neutral-0 px-2.5 py-1.5 text-xs text-neutral-900 placeholder:text-neutral-500 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                    />
                    <Button type="submit" variant="secondary" size="sm">
                      <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                      <span>Add task</span>
                    </Button>
                  </form>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
