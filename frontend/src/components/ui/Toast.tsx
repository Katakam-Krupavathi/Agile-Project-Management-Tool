import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

export type ToastTone = 'info' | 'success' | 'error';

export interface ToastAction {
  label: string;
  onClick: () => void;
}

interface ToastItem {
  id: number;
  tone: ToastTone;
  message: string;
  action?: ToastAction;
}

interface ToastContextValue {
  pushToast: (message: string, tone?: ToastTone, action?: ToastAction) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const pushToast = useCallback(
    (message: string, tone: ToastTone = 'info', action?: ToastAction) => {
      const id = Date.now() + Math.floor(Math.random() * 1000);
      setToasts((prev) => [...prev, { id, tone, message, action }]);
      window.setTimeout(() => dismiss(id), action ? 8000 : 4500);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ pushToast }}>
      {children}
      <div
        aria-live="polite"
        className="fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role={toast.tone === 'error' ? 'alert' : 'status'}
            className={[
              'flex items-start gap-2.5 rounded border p-3 text-sm shadow-md',
              toast.tone === 'error'
                ? 'border-brand bg-brand text-neutral-0'
                : toast.tone === 'success'
                  ? 'border-accent-200 bg-neutral-0 text-neutral-900'
                  : 'border-neutral-200 bg-neutral-0 text-neutral-900',
            ].join(' ')}
          >
            {toast.tone === 'error' && (
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-neutral-0" aria-hidden="true" />
            )}
            {toast.tone === 'success' && (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
            )}
            {toast.tone === 'info' && (
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
            )}
            <div className="flex-1 space-y-1.5">
              <p className="leading-snug">{toast.message}</p>
              {toast.action && (
                <button
                  type="button"
                  onClick={() => {
                    toast.action?.onClick();
                    dismiss(toast.id);
                  }}
                  className={[
                    'rounded border px-2 py-0.5 text-xs font-semibold transition-colors',
                    toast.tone === 'error'
                      ? 'border-neutral-0/40 bg-neutral-0/10 text-neutral-0 hover:bg-neutral-0/20'
                      : 'border-brand bg-brand-50 text-brand hover:bg-brand-100',
                  ].join(' ')}
                >
                  {toast.action.label}
                </button>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
              className="rounded p-0.5 opacity-80 hover:opacity-100"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
}
