// 认证 store/context：登录、登出、当前用户、角色判断

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { clearCsrfToken, isMockMode, apiPost } from "@/lib/api";
import { mockLogin } from "@/lib/mock";
import type { CurrentUserLike } from "@/lib/mock";
import type { Role } from "@/lib/types";

const USER_KEY = "hostguard.user";

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  role: Role;
}

function toAuthUser(u: CurrentUserLike): AuthUser {
  return { id: u.id, username: u.username, display_name: u.display_name, role: u.role };
}

function loadStoredUser(): AuthUser | null {
  try {
    const raw = window.sessionStorage.getItem(USER_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthUser;
    if (!parsed || typeof parsed.username !== "string") return null;
    return parsed;
  } catch {
    return null;
  }
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(loadStoredUser);

  const login = useCallback(async (username: string, password: string): Promise<AuthUser> => {
    let next: AuthUser;
    if (isMockMode()) {
      const res = await mockLogin(username, password);
      next = toAuthUser(res.user);
    } else {
      const res = await apiPost<{ user: CurrentUserLike }>("/auth/login", { username, password });
      next = toAuthUser(res.user);
    }
    window.sessionStorage.setItem(USER_KEY, JSON.stringify(next));
    setUser(next);
    return next;
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    try {
      if (!isMockMode()) await apiPost("/auth/logout");
    } finally {
      clearCsrfToken();
      window.sessionStorage.removeItem(USER_KEY);
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isAuthenticated: user !== null, login, logout }),
    [user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth 必须在 <AuthProvider> 内使用");
  return ctx;
}

/** 角色权限判定，与 contracts/conventions.md 对齐 */
export function roleAtLeast(role: Role, minimum: Role): boolean {
  const order: Role[] = ["viewer", "analyst", "admin"];
  return order.indexOf(role) >= order.indexOf(minimum);
}
