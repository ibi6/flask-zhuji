// 路由守卫：登录保护 + 角色保护

import { Navigate, Outlet, useLocation } from "react-router-dom";
import { roleAtLeast, useAuth } from "@/store/auth";
import type { Role } from "@/lib/types";

export function ProtectedRoute() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

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
  const { isAuthenticated } = useAuth();
  if (isAuthenticated) {
    return <Navigate to="/overview" replace />;
  }
  return <Outlet />;
}
