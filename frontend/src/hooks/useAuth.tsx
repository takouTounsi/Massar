import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import { getAccessToken, setAccessToken, subscribeToToken } from "../api/client";
import { getMe, login, logout, refreshSession, register } from "../api/auth";

/**
 * Three explicit auth states. The reload-redirect bug was caused by collapsing
 * "unknown" (we haven't finished restoring the session yet) into
 * "unauthenticated", so the guard redirected before the boot refresh resolved.
 */
export type AuthStatus = "unknown" | "authenticated" | "unauthenticated";

type AuthContextValue = ReturnType<typeof useAuthState>;

const AuthContext = createContext<AuthContextValue | null>(null);

function useAuthState() {
  const queryClient = useQueryClient();
  // Token is rehydrated synchronously from localStorage in api/client, so on a
  // hard refresh it is already present here on the very first render.
  const token = useSyncExternalStore(subscribeToToken, getAccessToken, getAccessToken);
  const didBootstrap = useRef(false);

  const meQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: getMe,
    enabled: Boolean(token),
    retry: false
  });
  const refreshMutation = useMutation({
    mutationFn: refreshSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["auth", "me"] }),
    onError: () => setAccessToken(null)
  });
  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["auth", "me"] })
  });
  const registerMutation = useMutation({
    mutationFn: register
  });
  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => queryClient.clear()
  });

  // Boot/rehydrate exactly once: when there is no in-memory token (try the
  // httpOnly refresh cookie) or the persisted token turned out to be stale
  // (getMe failed → try to mint a fresh one before giving up).
  const needsBootstrap = !token || meQuery.isError;
  useEffect(() => {
    if (needsBootstrap && !didBootstrap.current && refreshMutation.isIdle) {
      didBootstrap.current = true;
      refreshMutation.mutate();
    }
  }, [needsBootstrap, refreshMutation]);

  const refreshSettled = refreshMutation.isSuccess || refreshMutation.isError;
  // Still trying to restore a session → unknown, never redirect.
  const isBootstrapping = !token && !refreshSettled;
  const isLoading = isBootstrapping || (Boolean(token) && meQuery.isLoading);
  const isAuthenticated = Boolean(token);
  const status: AuthStatus = isLoading ? "unknown" : isAuthenticated ? "authenticated" : "unauthenticated";

  return {
    token,
    user: meQuery.data ?? loginMutation.data?.user ?? null,
    status,
    isAuthenticated,
    isLoading,
    meQuery,
    loginMutation,
    registerMutation,
    logoutMutation,
    refreshMutation
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const value = useAuthState();
  const memo = useMemo(() => value, [
    value.token,
    value.user,
    value.status,
    value.isAuthenticated,
    value.isLoading,
    value.meQuery,
    value.loginMutation,
    value.registerMutation,
    value.logoutMutation,
    value.refreshMutation
  ]);
  return <AuthContext.Provider value={memo}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside an AuthProvider");
  }
  return context;
}
