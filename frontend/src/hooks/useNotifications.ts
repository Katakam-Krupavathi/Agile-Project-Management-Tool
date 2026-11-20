import { useEffect } from 'react';
import { type QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, notificationsApi } from '../lib/api';
import type { Notification } from '../lib/types';
import { useToast } from '../components/ui';

export const NOTIFICATIONS_KEY = ['notifications'] as const;

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const INITIAL_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30000;

interface StreamSubscriber {
  queryClient: QueryClient;
  pushToast: (message: string, variant?: 'info' | 'success' | 'error') => void;
}

let activeSource: EventSource | null = null;
let reconnectTimer: number | null = null;
let lastEventId: string | null = null;
let reconnectAttempt = 0;
let stoppedOnUnauthorized = false;
let nextSubscriberId = 1;
const subscribers = new Map<number, StreamSubscriber>();

function clearReconnectTimer() {
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function closeActiveSource() {
  clearReconnectTimer();
  if (activeSource !== null) {
    activeSource.close();
    activeSource = null;
  }
}

export function resetNotificationStreamForTests() {
  closeActiveSource();
  subscribers.clear();
  lastEventId = null;
  reconnectAttempt = 0;
  stoppedOnUnauthorized = false;
}

function probeUnauthorizedAndStopIf401() {
  if (typeof fetch !== 'function') return;
  void fetch(`${API_BASE}/auth/me`, { credentials: 'include' })
    .then((res) => {
      if (res.status === 401) {
        stoppedOnUnauthorized = true;
        closeActiveSource();
      }
    })
    .catch(() => {
      // Transient network error; allow scheduled backoff reconnect to proceed.
    });
}

function ensureSharedStreamConnected() {
  if (
    stoppedOnUnauthorized ||
    subscribers.size === 0 ||
    activeSource !== null ||
    typeof EventSource === 'undefined'
  ) {
    return;
  }

  clearReconnectTimer();
  const url = lastEventId
    ? `${API_BASE}/notifications/stream?last_event_id=${encodeURIComponent(lastEventId)}`
    : `${API_BASE}/notifications/stream`;

  const source = new EventSource(url, { withCredentials: true });
  activeSource = source;

  source.onopen = () => {
    reconnectAttempt = 0;
  };

  source.addEventListener('notification', (event) => {
    reconnectAttempt = 0;
    const messageEvent = event as MessageEvent<string>;
    if (messageEvent.lastEventId) {
      lastEventId = messageEvent.lastEventId;
    }

    let parsed: Notification | null = null;
    try {
      parsed = JSON.parse(messageEvent.data) as Notification;
    } catch {
      // ignore malformed payload
    }

    const firstSubscriber = subscribers.values().next().value;
    if (parsed && !parsed.read_at && firstSubscriber) {
      firstSubscriber.pushToast(parsed.title, 'info');
    }

    const seenClients = new Set<QueryClient>();
    for (const sub of subscribers.values()) {
      if (!seenClients.has(sub.queryClient)) {
        seenClients.add(sub.queryClient);
        sub.queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
      }
    }
  });

  source.onerror = (event: Event) => {
    closeActiveSource();
    if (subscribers.size === 0 || stoppedOnUnauthorized) {
      return;
    }

    const status = (event as { status?: number })?.status;
    if (status === 401) {
      stoppedOnUnauthorized = true;
      return;
    }

    const delay = Math.min(
      INITIAL_RECONNECT_DELAY_MS * 2 ** reconnectAttempt,
      MAX_RECONNECT_DELAY_MS,
    );
    reconnectAttempt += 1;

    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      ensureSharedStreamConnected();
    }, delay);

    probeUnauthorizedAndStopIf401();
  };
}

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

    const wasEmpty = subscribers.size === 0;
    const subscriberId = nextSubscriberId++;
    subscribers.set(subscriberId, { queryClient, pushToast });

    if (wasEmpty) {
      stoppedOnUnauthorized = false;
      reconnectAttempt = 0;
    }
    ensureSharedStreamConnected();

    return () => {
      subscribers.delete(subscriberId);
      if (subscribers.size === 0) {
        closeActiveSource();
        reconnectAttempt = 0;
        stoppedOnUnauthorized = false;
      }
    };
  }, [enabled, queryClient, pushToast]);
}
