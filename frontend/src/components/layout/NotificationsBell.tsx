import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCheck } from 'lucide-react';
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  useNotificationStream,
} from '../../hooks/useNotifications';
import { parseUtcTimestamp } from '../../lib/labels';
import type { Notification } from '../../lib/types';

export function NotificationsBell() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const { data, isLoading } = useNotifications(true);
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();
  useNotificationStream(true);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  const items = data?.items ?? [];
  const unreadCount = data?.unread_count ?? 0;

  const handleOpenNotification = (item: Notification) => {
    if (!item.read_at) {
      markRead.mutate(item.id);
    }
    setOpen(false);
    if (item.project_id) {
      if (item.entity_type === 'story' && item.entity_id) {
        navigate(`/projects/${item.project_id}?story=${item.entity_id}`);
      } else if (item.entity_type === 'task' && item.entity_id) {
        navigate(`/projects/${item.project_id}?task=${item.entity_id}`);
      } else {
        navigate(`/projects/${item.project_id}`);
      }
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label={unreadCount > 0 ? `Notifications (${unreadCount} unread)` : 'Notifications'}
        aria-expanded={open}
        className="relative inline-flex h-9 w-9 items-center justify-center rounded border border-neutral-200 bg-neutral-0 text-neutral-900 hover:bg-neutral-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
      >
        <Bell className="h-4 w-4" aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 inline-flex min-w-[18px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-bold leading-4 text-neutral-0">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications list"
          className="absolute right-0 z-40 mt-2 w-80 overflow-hidden rounded border border-neutral-200 bg-neutral-0 shadow-lg sm:w-96"
        >
          <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-3">
            <span className="text-sm font-semibold text-neutral-900">
              Notifications {unreadCount > 0 ? `(${unreadCount})` : ''}
            </span>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => markAllRead.mutate()}
                disabled={markAllRead.isPending}
                className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:underline disabled:opacity-50"
              >
                <CheckCheck className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Mark all read</span>
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {isLoading ? (
              <p className="px-4 py-6 text-center text-xs text-neutral-500">Loading…</p>
            ) : items.length === 0 ? (
              <p className="px-4 py-8 text-center text-xs text-neutral-500">
                You are all caught up.
              </p>
            ) : (
              <ul className="divide-y divide-neutral-200">
                {items.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => handleOpenNotification(item)}
                      className={[
                        'flex w-full items-start gap-2.5 px-4 py-3 text-left transition-colors hover:bg-neutral-50',
                        !item.read_at ? 'bg-brand-50/40' : 'bg-neutral-0',
                      ].join(' ')}
                    >
                      <span
                        aria-hidden="true"
                        className={[
                          'mt-1.5 h-2 w-2 shrink-0 rounded-full',
                          !item.read_at ? 'bg-accent' : 'bg-neutral-200',
                        ].join(' ')}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium text-neutral-900">{item.title}</p>
                        {item.body && (
                          <p className="mt-0.5 line-clamp-2 text-xs text-neutral-500">
                            {item.body}
                          </p>
                        )}
                        <p className="mt-1 text-[11px] text-neutral-500">
                          {parseUtcTimestamp(item.created_at).toLocaleString()}
                        </p>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
