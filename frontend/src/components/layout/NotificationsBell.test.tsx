import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../ui';
import { NotificationsBell } from './NotificationsBell';
import {
  resetNotificationStreamForTests,
  useNotificationStream,
} from '../../hooks/useNotifications';
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

  afterEach(() => {
    resetNotificationStreamForTests();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('reuses a single EventSource per tab, backs off reconnects, and stops retrying on 401', async () => {
    vi.useFakeTimers();

    class MockEventSource {
      static instances: MockEventSource[] = [];
      url: string;
      closed = false;
      onopen: (() => void) | null = null;
      onerror: ((event: Event) => void) | null = null;

      constructor(url: string) {
        this.url = url;
        MockEventSource.instances.push(this);
      }

      addEventListener() {}

      close() {
        this.closed = true;
      }
    }

    const fetchMock = vi.fn().mockResolvedValue({ status: 200 });
    vi.stubGlobal('EventSource', MockEventSource);
    vi.stubGlobal('fetch', fetchMock);

    function StreamConsumer() {
      useNotificationStream(true);
      return null;
    }

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const { unmount } = render(
      <QueryClientProvider client={qc}>
        <ToastProvider>
          <StreamConsumer />
          <StreamConsumer />
        </ToastProvider>
      </QueryClientProvider>,
    );

    // Two mounted consumers in the same tab reuse one EventSource
    expect(MockEventSource.instances).toHaveLength(1);

    // First error schedules reconnect after 1000ms (initial backoff)
    act(() => {
      MockEventSource.instances[0].onerror?.(new Event('error'));
    });
    expect(MockEventSource.instances[0].closed).toBe(true);

    act(() => {
      vi.advanceTimersByTime(999);
    });
    expect(MockEventSource.instances).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(MockEventSource.instances).toHaveLength(2);

    // Second consecutive error backs off to 2000ms
    act(() => {
      MockEventSource.instances[1].onerror?.(new Event('error'));
    });
    act(() => {
      vi.advanceTimersByTime(1999);
    });
    expect(MockEventSource.instances).toHaveLength(2);

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(MockEventSource.instances).toHaveLength(3);

    // 401 response stops all further reconnects
    fetchMock.mockResolvedValueOnce({ status: 401 });
    await act(async () => {
      MockEventSource.instances[2].onerror?.(new Event('error'));
      await Promise.resolve();
    });

    act(() => {
      vi.advanceTimersByTime(60000);
    });
    expect(MockEventSource.instances).toHaveLength(3);

    unmount();
  });
});
