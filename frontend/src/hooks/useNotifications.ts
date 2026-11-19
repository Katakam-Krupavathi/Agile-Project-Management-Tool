import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, notificationsApi } from '../lib/api';
import type { Notification } from '../lib/types';
import { useToast } from '../components/ui';

export const NOTIFICATIONS_KEY = ['notifications'] as const;

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export function useNotifications(enabled = true) {
  return useQuery({
    queryKey: NOTIFICATIONS_KEY,
    queryFn: () => notificationsApi.list(30),
    enabled,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: notificationsApi.markRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
    },
    onError: (err) => {
      pushToast(
        err instanceof ApiError ? err.detail : 'Failed to mark notification read.',
        'error',
      );
    },
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
    },
    onError: (err) => {
      pushToast(
        err instanceof ApiError ? err.detail : 'Failed to mark all notifications read.',
        'error',
      );
    },
  });
}

export function useNotificationStream(enabled = true) {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  useEffect(() => {
    if (!enabled || typeof EventSource === 'undefined') return;

    let closed = false;
    let source: EventSource | null = null;
    let reconnectTimer: number | null = null;
    let lastEventId: string | null = null;

    const connect = () => {
      if (closed) return;
      const url = lastEventId
        ? `${API_BASE}/notifications/stream?last_event_id=${encodeURIComponent(lastEventId)}`
        : `${API_BASE}/notifications/stream`;

      source = new EventSource(url, { withCredentials: true });

      source.addEventListener('notification', (event) => {
        const messageEvent = event as MessageEvent<string>;
        if (messageEvent.lastEventId) {
          lastEventId = messageEvent.lastEventId;
        }
        try {
          const parsed = JSON.parse(messageEvent.data) as Notification;
          if (!parsed.read_at) {
            pushToast(parsed.title, 'info');
          }
        } catch {
          // ignore malformed payload
        }
        queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
      });

      source.onerror = () => {
        source?.close();
        source = null;
        if (!closed) {
          reconnectTimer = window.setTimeout(connect, 5000);
        }
      };
    };

    connect();

    return () => {
      closed = true;
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
      }
      source?.close();
    };
  }, [enabled, queryClient, pushToast]);
}
