import { describe, expect, it } from 'vitest';
import { parseQuickAdd } from './quickAddParser';
import type { ProjectMember } from './types';

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
  {
    id: 'm2',
    project_id: 'p1',
    user_id: 'u2',
    email: 'sam.chen@team.dev',
    name: 'Sam Chen',
    role: 'member',
    created_at: '2026-01-01T00:00:00Z',
  },
];

describe('parseQuickAdd', () => {
  it('parses title, assignee, priority, and ISO due date', () => {
    const res = parseQuickAdd('Implement OAuth flow @alex !high due:2026-12-15', MEMBERS);
    expect(res).toEqual({
      ok: true,
      value: {
        title: 'Implement OAuth flow',
        assigneeId: 'u1',
        priority: 'high',
        dueDate: '2026-12-15',
      },
    });
  });

  it('defaults priority to medium and supports due:today and due:tomorrow', () => {
    const ref = new Date(2026, 10, 20); // Nov 20, 2026
    const todayRes = parseQuickAdd('Write docs due:today', MEMBERS, ref);
    expect(todayRes).toEqual({
      ok: true,
      value: {
        title: 'Write docs',
        assigneeId: null,
        priority: 'medium',
        dueDate: '2026-11-20',
      },
    });

    const tomorrowRes = parseQuickAdd('Ship release @sam.chen !urgent due:tomorrow', MEMBERS, ref);
    expect(tomorrowRes).toEqual({
      ok: true,
      value: {
        title: 'Ship release',
        assigneeId: 'u2',
        priority: 'urgent',
        dueDate: '2026-11-21',
      },
    });
  });

  it('returns clear errors on unknown assignee, invalid priority, invalid date, or empty title', () => {
    const badAssignee = parseQuickAdd('Fix bug @nobody', MEMBERS);
    expect(badAssignee.ok).toBe(false);
    if (!badAssignee.ok) expect(badAssignee.error).toContain('@nobody');

    const badPriority = parseQuickAdd('Fix bug !critical', MEMBERS);
    expect(badPriority.ok).toBe(false);
    if (!badPriority.ok) expect(badPriority.error).toContain('!critical');

    const badDate = parseQuickAdd('Fix bug due:2026-02-31', MEMBERS);
    expect(badDate.ok).toBe(false);
    if (!badDate.ok) expect(badDate.error).toContain('due:2026-02-31');

    const emptyTitle = parseQuickAdd('@alex !high', MEMBERS);
    expect(emptyTitle.ok).toBe(false);
  });
});
