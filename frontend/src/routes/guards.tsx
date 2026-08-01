// 路由守卫：登录保护 + 角色保护

import { Navigate, Outlet, useLocation } from "react-router-dom";
import { FluxScene } from "@/components/FluxScene";
import { roleAtLeast, useAuth } from "@/store/auth";
import type { Role } from "@/lib/types";

function AuthLoading() {
  return (
    <>
      <FluxScene />
      <div className="loading-screen">
        <p>正在验证会话…</p>
      </div>
    </>
  );
}

export function ProtectedRoute() {
  const { isAuthenticated, initializing } = useAuth();
  const location = useLocation();

  if (initializing) return <AuthLoading />;
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}

export function RoleRoute({ minRole }: { minRole: Role }) {
  const { user } = useAuth();

  if (!user || !roleAtLeast(user.role, minRole)) {
    return <Navigate to="/overview" replace />;
  }
  return <Outlet />;
}

export function GuestRoute() {
  const { isAuthenticated, initializing } = useAuth();
  if (initializing) return <AuthLoading />;
  if (isAuthenticated) {
    return <Navigate to="/overview" replace />;
  }
  return <Outlet />;
}
