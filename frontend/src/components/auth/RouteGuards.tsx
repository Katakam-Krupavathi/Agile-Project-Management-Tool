import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useCurrentUser } from '../../hooks/useAuth';
import { ErrorState, Skeleton } from '../ui';

export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { data: user, isLoading, isError, error, refetch } = useCurrentUser();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-50 p-6">
        <div className="w-full max-w-sm space-y-3 rounded border border-neutral-200 bg-neutral-0 p-6">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-50 p-6">
        <div className="w-full max-w-md">
          <ErrorState
            title="Unable to verify session"
            message={error instanceof Error ? error.message : 'Network error'}
            onRetry={() => refetch()}
          />
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return <>{children}</>;
}

export function GuestOnly({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useCurrentUser();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-50 p-6">
        <Skeleton className="h-8 w-48" />
      </div>
    );
  }

  if (user) {
    return <Navigate to="/projects" replace />;
  }

  return <>{children}</>;
}
