import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, authApi } from '../lib/api';
import { useToast } from '../components/ui';

export const AUTH_ME_KEY = ['auth', 'me'] as const;

export function useCurrentUser() {
  return useQuery({
    queryKey: AUTH_ME_KEY,
    queryFn: async () => {
      try {
        return await authApi.me();
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          return null;
        }
        throw err;
      }
    },
    staleTime: 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: authApi.login,
    onSuccess: (session) => {
      queryClient.setQueryData(AUTH_ME_KEY, session.user);
      pushToast(`Welcome back, ${session.user.name}.`, 'success');
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.detail : 'Unable to sign in.';
      pushToast(msg, 'error');
    },
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: async (payload: { email: string; name: string; password: string }) => {
      await authApi.register(payload);
      return authApi.login({ email: payload.email, password: payload.password });
    },
    onSuccess: (session) => {
      queryClient.setQueryData(AUTH_ME_KEY, session.user);
      pushToast('Account created successfully.', 'success');
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.detail : 'Unable to create account.';
      pushToast(msg, 'error');
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const { pushToast } = useToast();

  return useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.clear();
      queryClient.setQueryData(AUTH_ME_KEY, null);
      pushToast('Signed out.', 'info');
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.detail : 'Unable to sign out.';
      pushToast(msg, 'error');
    },
  });
}
