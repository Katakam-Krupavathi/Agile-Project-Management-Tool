import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { OutlineView } from './OutlineView';
import { QuickAddBar } from './QuickAddBar';
import { StoryFocusDrawer } from './StoryFocusDrawer';
import type { ActivityLog, ProjectMember, StoryTreeNode } from '../../lib/types';

const MEMBERS: ProjectMember[] = [
  {
    id: 'm1',
    project_id: 'p1',
    user_id: 'u1',
    email: 'alex@team.dev',
    name: 'Alex Rivera',
    role: 'owner',
    created_at: '2026-01-01T00:00:00Z',
  },
];

const SAMPLE_NODE: StoryTreeNode = {
  story: {
    id: 's1',
    project_id: 'p1',
    number: 1,
    key: 'APM-1',
    title: 'Implement Kanban board',
    description: 'Support drag and drop',
    acceptance_criteria: 'Persists on refresh',
    status: 'in_progress',
    priority: 'high',
    story_points: 5,
    assignee_id: 'u1',
    position: 1024,
    version: 2,
    created_by: 'u1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
  rollup: {
    total_tasks: 2,
    done_tasks: 1,
    blocked_tasks: 1,
    overdue_tasks: 0,
    progress_pct: 50,
    is_blocked: true,
    suggested_status: null,
  },
  tasks: [
    {
      id: 't1',
      story_id: 's1',
      title: 'Setup dnd-kit',
      description: null,
      status: 'done',
      assignee_id: 'u1',
      estimate_hours: 2,
      due_date: null,
      position: 1024,
      version: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 't2',
      story_id: 's1',
      title: 'Fix column lock',
      description: null,
      status: 'blocked',
      assignee_id: 'u1',
      estimate_hours: 2,
      due_date: '2026-12-01',
      position: 2048,
      version: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
};

const ACTIVITY: ActivityLog[] = [
  {
    id: 'a1',
    project_id: 'p1',
    actor_id: 'u1',
    actor_name: 'Alex Rivera',
    entity_type: 'story',
    entity_id: 's1',
    action: 'story.created',
    details: { key: 'APM-1' },
    created_at: '2026-01-01T10:00:00Z',
  },
];

describe('QuickAddBar', () => {
  it('shows inline parse error on invalid token and submits valid input', async () => {
    const user = userEvent.setup();
    const onQuickAdd = vi.fn().mockResolvedValue(undefined);

    render(<QuickAddBar members={MEMBERS} onQuickAdd={onQuickAdd} />);

    const input = screen.getByLabelText('Quick-add story');
    await user.type(input, 'Broken story !invalid');
    await user.click(screen.getByRole('button', { name: /add story/i }));

    expect(screen.getByRole('alert')).toHaveTextContent('!invalid');
    expect(onQuickAdd).not.toHaveBeenCalled();

    await user.clear(input);
    await user.type(input, 'Build reports @alex !urgent due:2026-12-05');
    await user.click(screen.getByRole('button', { name: /add story/i }));

    expect(onQuickAdd).toHaveBeenCalledWith({
      title: 'Build reports',
      assigneeId: 'u1',
      priority: 'urgent',
      dueDate: '2026-12-05',
    });
  });
});

describe('OutlineView', () => {
  it('renders blocked indicator, expands tasks, and hides edit controls for viewers', async () => {
    const user = userEvent.setup();
    const noop = vi.fn();

    render(
      <OutlineView
        stories={[SAMPLE_NODE]}
        members={MEMBERS}
        canEdit={false}
        onUpdateStory={noop}
        onCreateTask={noop}
        onUpdateTask={noop}
      />,
    );

    expect(screen.getByText('APM-1')).toBeInTheDocument();
    expect(screen.getByText('Blocked')).toBeInTheDocument();
    expect(screen.getByText('50%')).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /expand apm-1 tasks/i }));
    expect(screen.getByText('Setup dnd-kit')).toBeInTheDocument();
    expect(screen.getByText('Fix column lock')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/add a task/i)).not.toBeInTheDocument();
  });
});

describe('StoryFocusDrawer', () => {
  it('hides edit and task mutation controls for viewers and renders timeline', () => {
    const noop = vi.fn();

    render(
      <StoryFocusDrawer
        node={SAMPLE_NODE}
        members={MEMBERS}
        activity={ACTIVITY}
        canEdit={false}
        onClose={noop}
        onUpdateStory={noop}
        onDeleteStory={noop}
        onCreateTask={noop}
        onUpdateTask={noop}
        onMoveTask={noop}
        onDeleteTask={noop}
      />,
    );

    expect(screen.getByText('Implement Kanban board')).toBeInTheDocument();
    expect(screen.getByText('story.created')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /save changes/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /delete story/i })).not.toBeInTheDocument();
  });

  it('shows save and add-task controls for members/owners', () => {
    const noop = vi.fn();

    render(
      <StoryFocusDrawer
        node={SAMPLE_NODE}
        members={MEMBERS}
        activity={ACTIVITY}
        canEdit={true}
        onClose={noop}
        onUpdateStory={noop}
        onDeleteStory={noop}
        onCreateTask={noop}
        onUpdateTask={noop}
        onMoveTask={noop}
        onDeleteTask={noop}
      />,
    );

    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /delete story/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /add task/i })).toBeInTheDocument();
  });
});
