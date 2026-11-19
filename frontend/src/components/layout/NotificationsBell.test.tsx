import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../ui';
import { NotificationsBell } from './NotificationsBell';
import { notificationsApi } from '../../lib/api';

vi.mock('../../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../lib/api')>();
  return {
    ...actual,
    notificationsApi: {
      list: vi.fn(),
      markRead: vi.fn(),
      markAllRead: vi.fn(),
    },
  };
});

describe('NotificationsBell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(notificationsApi.list).mockResolvedValue({
      items: [
        {
          id: 'n1',
          user_id: 'u1',
          project_id: 'p1',
          type: 'task.assigned',
          title: 'Assigned task: Wire SSE',
          body: 'You were assigned to Wire SSE.',
          entity_type: 'task',
          entity_id: 't1',
          read_at: null,
          created_at: '2026-11-20T10:00:00Z',
        },
        {
          id: 'n2',
          user_id: 'u1',
          project_id: 'p1',
          type: 'story.assigned',
          title: 'Assigned to APM-1',
          body: null,
          entity_type: 'story',
          entity_id: 's1',
          read_at: null,
          created_at: '2026-11-20T09:00:00Z',
        },
      ],
      next_cursor: null,
      has_more: false,
      unread_count: 2,
    });
    vi.mocked(notificationsApi.markRead).mockResolvedValue({
      id: 'n1',
      user_id: 'u1',
      project_id: 'p1',
      type: 'task.assigned',
      title: 'Assigned task: Wire SSE',
      body: 'You were assigned to Wire SSE.',
      entity_type: 'task',
      entity_id: 't1',
      read_at: '2026-11-20T10:05:00Z',
      created_at: '2026-11-20T10:00:00Z',
    });
    vi.mocked(notificationsApi.markAllRead).mockResolvedValue({ updated: 2 });
  });

  it('displays unread count, opens dropdown, marks individual and all read', async () => {
    const user = userEvent.setup();
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={qc}>
        <ToastProvider>
          <MemoryRouter>
            <NotificationsBell />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );

    const bell = await screen.findByRole('button', { name: /notifications \(2 unread\)/i });
    expect(bell).toHaveTextContent('2');

    await user.click(bell);
    expect(screen.getByText('Assigned task: Wire SSE')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /mark all read/i }));
    expect(notificationsApi.markAllRead).toHaveBeenCalledTimes(1);

    await user.click(screen.getByText('Assigned task: Wire SSE'));
    expect(notificationsApi.markRead).toHaveBeenCalledTimes(1);
    expect(vi.mocked(notificationsApi.markRead).mock.calls[0][0]).toBe('n1');
  });
});
