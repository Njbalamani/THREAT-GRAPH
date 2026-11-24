import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authApi, clearToken, getToken, setToken } from "./api";
import type { UserOut, UserRole } from "./types";

interface AuthContextValue {
  user: UserOut | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  canWrite: boolean;
  isAdmin: boolean;
  hasRole: (...roles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setReady(true);
      return;
    }
    try {
      setUser(await authApi.me());
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(
    async (username: string, password: string) => {
      const token = await authApi.login(username, password);
      setToken(token.access_token);
      await refresh();
    },
    [refresh],
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(() => {
    const roles = user ? [user.role] : [];
    return {
      user,
      ready,
      login,
      logout,
      refresh,
      canWrite: roles.includes("admin") || roles.includes("analyst"),
      isAdmin: roles.includes("admin"),
      hasRole: (...allowed: UserRole[]) => roles.some((role) => allowed.includes(role)),
    };
  }, [user, ready, login, logout, refresh]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
