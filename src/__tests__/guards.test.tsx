// 路由守卫测试

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { ProtectedRoute, RoleRoute } from "@/routes/guards";
import { AuthProvider, type AuthUser } from "@/store/auth";

function setUser(user: AuthUser | null) {
  if (user) {
    sessionStorage.setItem("hostguard.user", JSON.stringify(user));
  } else {
    sessionStorage.removeItem("hostguard.user");
  }
}

function renderRouter(initialPath: string, extra?: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <AuthProvider>
          <Routes>
            <Route element={<ProtectedRoute />}>
              <Route element={<RoleRoute minRole="admin" />}>
                <Route path="/admin-only" element={<p>admin 内容</p>} />
              </Route>
              <Route path="/dashboard" element={<p>仪表盘</p>} />
            </Route>
            <Route path="/login" element={<p>登录页</p>} />
            <Route path="/overview" element={<p>总览页</p>} />
          </Routes>
          {extra}
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const adminUser: AuthUser = {
  id: "u1",
  username: "admin",
  display_name: "管理员",
  role: "admin",
};

const viewerUser: AuthUser = {
  id: "u2",
  username: "viewer",
  display_name: "访客",
  role: "viewer",
};

describe("路由守卫", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("未登录访问受保护页面时重定向到 /login", () => {
    setUser(null);
    renderRouter("/dashboard");
    expect(screen.getByText("登录页")).toBeInTheDocument();
  });

  it("已登录用户可以访问受保护页面", () => {
    setUser(viewerUser);
    renderRouter("/dashboard");
    expect(screen.getByText("仪表盘")).toBeInTheDocument();
  });

  it("viewer 角色不能访问 admin 页面，重定向到总览", () => {
    setUser(viewerUser);
    renderRouter("/admin-only");
    expect(screen.getByText("总览页")).toBeInTheDocument();
  });

  it("admin 角色可以访问 admin 页面", () => {
    setUser(adminUser);
    renderRouter("/admin-only");
    expect(screen.getByText("admin 内容")).toBeInTheDocument();
  });
});
