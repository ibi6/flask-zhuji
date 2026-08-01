// 登录页测试

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "@/pages/LoginPage";
import { AuthProvider } from "@/store/auth";
import { ThemeProvider } from "@/store/theme";

// mock 模式下 mockLogin 会被调用
vi.mock("@/lib/mock", () => ({
  MOCK_ACTIVE: true,
  mockLogin: vi.fn(async (username: string, password: string) => {
    if (!username || !password) throw new Error("请输入用户名和密码");
    const role = username === "admin" ? "admin" : username === "analyst" ? "analyst" : "viewer";
    return {
      token: `mock-${username}`,
      user: { id: "u1", username, display_name: username, role },
    };
  }),
}));

// isMockMode 返回 true
vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return { ...actual, isMockMode: () => true };
});

function renderLogin() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ThemeProvider>
          <AuthProvider>
            <LoginPage />
          </AuthProvider>
        </ThemeProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("渲染登录表单与角色入口", () => {
    renderLogin();
    expect(screen.getByRole("heading", { name: "安全登录" })).toBeInTheDocument();
    expect(screen.getByLabelText("用户名")).toBeInTheDocument();
    expect(screen.getByLabelText("密码")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "登 录" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "演示角色选择" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /以管理员身份登录/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /以分析员身份登录/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /以只读用户身份登录/ })).toBeInTheDocument();
  });

  it("空表单提交显示错误", async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.click(screen.getByRole("button", { name: "登 录" }));
    expect(screen.getByText("请输入用户名和密码")).toBeInTheDocument();
  });

  it("成功登录后显示开发模式提示", async () => {
    const user = userEvent.setup();
    renderLogin();
    // 开发模式提示应存在
    expect(screen.getByText(/开发模式/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("用户名"), "admin");
    await user.type(screen.getByLabelText("密码"), "admin123");
    await user.click(screen.getByRole("button", { name: "登 录" }));
    // 登录成功后 user 信息写入 sessionStorage
    const stored = sessionStorage.getItem("hostguard.user");
    expect(stored).toBeTruthy();
    const parsed = JSON.parse(stored!);
    expect(parsed.username).toBe("admin");
  });

  it("仅输入用户名时提示错误", async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.type(screen.getByLabelText("用户名"), "admin");
    await user.click(screen.getByRole("button", { name: "登 录" }));
    expect(screen.getByText("请输入用户名和密码")).toBeInTheDocument();
  });
});
