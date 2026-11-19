import { useEffect } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { ToastProvider, useToast } from './components/ui';
import { AUTH_ME_KEY } from './hooks/useAuth';
import { setUnauthorizedHandler } from './lib/api';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

function AuthRedirectBridge() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { pushToast } = useToast();

  useEffect(() => {
    setUnauthorizedHandler(() => {
      qc.setQueryData(AUTH_ME_KEY, null);
      pushToast('Your session expired. Please sign in again.', 'error');
      navigate('/login', { replace: true });
    });
    return () => setUnauthorizedHandler(null);
  }, [navigate, qc, pushToast]);

  return null;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <AuthRedirectBridge />
          <Routes>
            <Route
              path="/"
              element={
                <main className="min-h-screen bg-neutral-50 flex items-center justify-center p-6">
                  <section className="w-full max-w-md rounded bg-neutral-0 border border-neutral-200 p-8 shadow-sm">
                    <div className="flex items-center gap-3">
                      <span
                        aria-hidden="true"
                        className="inline-flex h-8 w-8 items-center justify-center rounded bg-brand text-neutral-0 text-sm font-semibold"
                      >
                        AP
                      </span>
                      <h1 className="text-xl font-semibold tracking-tight text-brand">
                        Agile Project Management Tool
                      </h1>
                    </div>
                    <div className="mt-4 h-1 w-12 rounded bg-accent" aria-hidden="true" />
                  </section>
                </main>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
