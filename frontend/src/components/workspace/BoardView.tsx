import { useState } from 'react';
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCorners,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { AlertOctagon, CheckSquare, GripVertical } from 'lucide-react';
import { Avatar, Badge, ProgressRail } from '../ui';
import { STORY_PRIORITY_LABELS, STORY_STATUS_LABELS } from '../../lib/labels';
import type { ProjectMember, Story, StoryStatus, StoryTreeNode } from '../../lib/types';

const COLUMNS: StoryStatus[] = ['backlog', 'in_progress', 'in_review', 'done'];

export interface BoardViewProps {
  stories: StoryTreeNode[];
  members: ProjectMember[];
  canEdit: boolean;
  onSelectStory?: (storyId: string) => void;
  onMoveStory: (
    story: Story,
    target: { status: StoryStatus; before_id: string | null; after_id: string | null },
  ) => void;
}

function CardBody({
  node,
  assignee,
  canEdit,
  onSelectStory,
  dragHandleProps,
}: {
  node: StoryTreeNode;
  assignee?: ProjectMember;
  canEdit: boolean;
  onSelectStory?: (storyId: string) => void;
  dragHandleProps?: Record<string, unknown>;
}) {
  const { story, rollup } = node;
  return (
    <div className="rounded border border-neutral-200 bg-neutral-0 p-3 shadow-sm transition-colors hover:border-brand">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-xs font-semibold text-brand">{story.key}</span>
          <Badge variant={story.priority === 'urgent' ? 'brand' : 'outline'}>
            {STORY_PRIORITY_LABELS[story.priority]}
          </Badge>
          {rollup.is_blocked && (
            <Badge variant="brand">
              <AlertOctagon className="h-3 w-3" aria-hidden="true" />
              <span>Blocked</span>
            </Badge>
          )}
        </div>
        {canEdit && dragHandleProps && (
          <button
            type="button"
            aria-label={`Drag ${story.key}`}
            className="cursor-grab rounded p-0.5 text-neutral-500 hover:bg-neutral-50 hover:text-neutral-900 active:cursor-grabbing"
            {...dragHandleProps}
          >
            <GripVertical className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>

      {onSelectStory ? (
        <button
          type="button"
          onClick={() => onSelectStory(story.id)}
          className="mt-2 block w-full text-left text-sm font-medium text-neutral-900 hover:text-brand"
        >
          {story.title}
        </button>
      ) : (
        <p className="mt-2 text-sm font-medium text-neutral-900">{story.title}</p>
      )}

      <div className="mt-3 space-y-2">
        <ProgressRail value={rollup.progress_pct} />
        <div className="flex items-center justify-between text-xs text-neutral-500">
          <span className="inline-flex items-center gap-1 tabular-nums">
            <CheckSquare className="h-3.5 w-3.5" aria-hidden="true" />
            <span>
              {rollup.done_tasks}/{rollup.total_tasks}
            </span>
          </span>
          {assignee ? <Avatar name={assignee.name} size="sm" /> : <span>Unassigned</span>}
        </div>
      </div>
    </div>
  );
}

function SortableBoardCard({
  node,
  assignee,
  canEdit,
  onSelectStory,
}: {
  node: StoryTreeNode;
  assignee?: ProjectMember;
  canEdit: boolean;
  onSelectStory?: (storyId: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: node.story.id,
    disabled: !canEdit,
    data: { status: node.story.status },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div ref={setNodeRef} style={style}>
      <CardBody
        node={node}
        assignee={assignee}
        canEdit={canEdit}
        onSelectStory={onSelectStory}
        dragHandleProps={canEdit ? { ...attributes, ...listeners } : undefined}
      />
    </div>
  );
}

function BoardColumn({
  status,
  nodes,
  memberById,
  canEdit,
  onSelectStory,
}: {
  status: StoryStatus;
  nodes: StoryTreeNode[];
  memberById: Map<string, ProjectMember>;
  canEdit: boolean;
  onSelectStory?: (storyId: string) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `column:${status}`,
    data: { status },
  });

  return (
    <section
      ref={setNodeRef}
      aria-label={`${STORY_STATUS_LABELS[status]} column`}
      className={[
        'flex min-h-[380px] flex-col rounded border p-3 transition-colors',
        isOver ? 'border-accent bg-accent-50/40' : 'border-neutral-200 bg-neutral-50',
      ].join(' ')}
    >
      <header className="mb-3 flex items-center justify-between px-1">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-neutral-900">
          {STORY_STATUS_LABELS[status]}
        </h2>
        <Badge variant="outline">{nodes.length}</Badge>
      </header>

      <SortableContext items={nodes.map((n) => n.story.id)} strategy={verticalListSortingStrategy}>
        <div className="flex flex-1 flex-col gap-2.5">
          {nodes.length === 0 ? (
            <p className="rounded border border-dashed border-neutral-200 px-3 py-6 text-center text-xs text-neutral-500">
              No stories
            </p>
          ) : (
            nodes.map((node) => (
              <SortableBoardCard
                key={node.story.id}
                node={node}
                assignee={node.story.assignee_id ? memberById.get(node.story.assignee_id) : undefined}
                canEdit={canEdit}
                onSelectStory={onSelectStory}
              />
            ))
          )}
        </div>
      </SortableContext>
    </section>
  );
}

export function BoardView({
  stories,
  members,
  canEdit,
  onSelectStory,
  onMoveStory,
}: BoardViewProps) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const memberById = new Map(members.map((m) => [m.user_id, m]));
  const storyById = new Map(stories.map((n) => [n.story.id, n]));

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const grouped: Record<StoryStatus, StoryTreeNode[]> = {
    backlog: [],
    in_progress: [],
    in_review: [],
    done: [],
  };
  for (const node of stories) {
    grouped[node.story.status].push(node);
  }

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(String(event.active.id));
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveId(null);
    if (!canEdit) return;
    const { active, over } = event;
    if (!over) return;

    const activeStoryId = String(active.id);
    const overId = String(over.id);
    if (activeStoryId === overId) return;

    const activeNode = storyById.get(activeStoryId);
    if (!activeNode) return;

    let targetStatus: StoryStatus;
    let beforeId: string | null = null;
    let afterId: string | null = null;

    if (overId.startsWith('column:')) {
      targetStatus = overId.replace('column:', '') as StoryStatus;
      const targetList = grouped[targetStatus].filter((n) => n.story.id !== activeStoryId);
      beforeId = targetList.length > 0 ? targetList[targetList.length - 1].story.id : null;
      afterId = null;
    } else {
      const overNode = storyById.get(overId);
      if (!overNode) return;
      targetStatus = overNode.story.status;
      const targetList = grouped[targetStatus].filter((n) => n.story.id !== activeStoryId);
      const overIndex = targetList.findIndex((n) => n.story.id === overId);
      if (overIndex === -1) {
        beforeId = targetList.length > 0 ? targetList[targetList.length - 1].story.id : null;
      } else {
        beforeId = overIndex > 0 ? targetList[overIndex - 1].story.id : null;
        afterId = targetList[overIndex].story.id;
      }
    }

    onMoveStory(activeNode.story, {
      status: targetStatus,
      before_id: beforeId,
      after_id: afterId,
    });
  };

  const activeNode = activeId ? storyById.get(activeId) : undefined;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {COLUMNS.map((status) => (
          <BoardColumn
            key={status}
            status={status}
            nodes={grouped[status]}
            memberById={memberById}
            canEdit={canEdit}
            onSelectStory={onSelectStory}
          />
        ))}
      </div>

      <DragOverlay>
        {activeNode ? (
          <CardBody
            node={activeNode}
            assignee={
              activeNode.story.assignee_id
                ? memberById.get(activeNode.story.assignee_id)
                : undefined
            }
            canEdit={canEdit}
          />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
