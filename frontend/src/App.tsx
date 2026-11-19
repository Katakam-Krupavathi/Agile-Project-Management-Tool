import { useEffect } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { GuestOnly, RequireAuth } from './components/auth/RouteGuards';
import { ToastProvider, useToast } from './components/ui';
import { AUTH_ME_KEY } from './hooks/useAuth';
import { setUnauthorizedHandler } from './lib/api';
import { LoginPage } from './pages/LoginPage';
import { ProjectActivityPage } from './pages/ProjectActivityPage';
import { ProjectDetailPage } from './pages/ProjectDetailPage';
import { ProjectMembersPage } from './pages/ProjectMembersPage';
import { ProjectReportsPage } from './pages/ProjectReportsPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { RegisterPage } from './pages/RegisterPage';

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
              path="/login"
              element={
                <GuestOnly>
                  <LoginPage />
                </GuestOnly>
              }
            />
            <Route
              path="/register"
              element={
                <GuestOnly>
                  <RegisterPage />
                </GuestOnly>
              }
            />
            <Route
              path="/projects"
              element={
                <RequireAuth>
                  <ProjectsPage />
                </RequireAuth>
              }
            />
            <Route
              path="/projects/:projectId"
              element={
                <RequireAuth>
                  <ProjectDetailPage />
                </RequireAuth>
              }
            />
            <Route
              path="/projects/:projectId/activity"
              element={
                <RequireAuth>
                  <ProjectActivityPage />
                </RequireAuth>
              }
            />
            <Route
              path="/projects/:projectId/reports"
              element={
                <RequireAuth>
                  <ProjectReportsPage />
                </RequireAuth>
              }
            />
            <Route
              path="/projects/:projectId/members"
              element={
                <RequireAuth>
                  <ProjectMembersPage />
                </RequireAuth>
              }
            />
            <Route path="/" element={<Navigate to="/projects" replace />} />
            <Route path="*" element={<Navigate to="/projects" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
