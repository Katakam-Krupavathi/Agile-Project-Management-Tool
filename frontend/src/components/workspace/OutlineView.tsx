import { useState } from 'react';
import { AlertOctagon, Calendar, ChevronDown, ChevronRight, Clock } from 'lucide-react';
import { Avatar, Badge, EmptyState, ProgressRail } from '../ui';
import {
  isTaskOverdue,
  STORY_PRIORITY_LABELS,
  STORY_STATUS_LABELS,
  TASK_STATUS_LABELS,
} from '../../lib/labels';
import type { ProjectMember, StoryTreeNode } from '../../lib/types';

export interface OutlineViewProps {
  stories: StoryTreeNode[];
  members: ProjectMember[];
  onSelectStory?: (storyId: string) => void;
}

export function OutlineView({ stories, members, onSelectStory }: OutlineViewProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const memberById = new Map(members.map((m) => [m.user_id, m]));

  const toggleExpand = (storyId: string) => {
    setExpanded((prev) => ({ ...prev, [storyId]: !prev[storyId] }));
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

              {onSelectStory ? (
                <button
                  type="button"
                  onClick={() => onSelectStory(story.id)}
                  className="min-w-0 flex-1 truncate text-left text-sm font-medium text-neutral-900 hover:text-brand"
                >
                  {story.title}
                </button>
              ) : (
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-neutral-900">
                  {story.title}
                </span>
              )}

              <div className="flex flex-wrap items-center gap-2">
                {rollup.is_blocked && (
                  <Badge variant="brand">
                    <AlertOctagon className="h-3 w-3" aria-hidden="true" />
                    <span>Blocked</span>
                  </Badge>
                )}

                <Badge variant={story.status === 'done' ? 'accent' : 'neutral'}>
                  {STORY_STATUS_LABELS[story.status]}
                </Badge>

                <Badge variant={story.priority === 'urgent' ? 'brand' : 'outline'}>
                  {STORY_PRIORITY_LABELS[story.priority]}
                </Badge>

                {storyAssignee && <Avatar name={storyAssignee.name} size="sm" />}

                <div className="w-28">
                  <ProgressRail value={rollup.progress_pct} />
                </div>

                <span className="w-16 text-right text-xs tabular-nums text-neutral-500">
                  {rollup.done_tasks}/{rollup.total_tasks} tasks
                </span>
              </div>
            </div>

            {isOpen && (
              <div className="border-t border-neutral-200 bg-neutral-50 px-6 py-3">
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
                            <span
                              className={[
                                'truncate',
                                task.status === 'done'
                                  ? 'text-neutral-500 line-through'
                                  : 'text-neutral-900',
                              ].join(' ')}
                            >
                              {task.title}
                            </span>
                          </div>

                          <div className="flex items-center gap-2.5 text-xs text-neutral-500">
                            {task.estimate_hours !== null && (
                              <span className="tabular-nums">{task.estimate_hours}h</span>
                            )}
                            {task.due_date && (
                              <span className="inline-flex items-center gap-1">
                                {overdue ? (
                                  <Badge variant="brand">
                                    <Clock className="h-3 w-3" aria-hidden="true" />
                                    <span>Overdue · {task.due_date}</span>
                                  </Badge>
                                ) : (
                                  <>
                                    <Calendar className="h-3.5 w-3.5" aria-hidden="true" />
                                    <span>{task.due_date}</span>
                                  </>
                                )}
                              </span>
                            )}
                            {taskAssignee && <Avatar name={taskAssignee.name} size="sm" />}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
