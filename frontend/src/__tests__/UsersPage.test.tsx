// 用户管理页测试

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { UsersPage } from "@/pages/UsersPage";
import { AuthProvider, type AuthUser } from "@/store/auth";
import type { Page, User } from "@/lib/types";

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
}));

vi.mock("@/lib/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/api")>();
  return {
    ...actual,
    apiGet: mocks.apiGet,
    apiPost: mocks.apiPost,
    apiPatch: mocks.apiPatch,
    apiDelete: mocks.apiDelete,
    isMockMode: () => true,
    refreshCsrf: vi.fn(async () => undefined),
  };
});

const users: User[] = [
  {
    id: "u1",
    username: "zhang.yu",
    display_name: "张宇",
    email: "zhang@example.com",
    role: "analyst",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    last_login_at: "2026-07-01T00:00:00Z",
  },
];

const adminUser: AuthUser = { id: "u-admin", username: "admin", display_name: "管理员", role: "admin" };

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuthProvider>
          <UsersPage />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function setUser(user: AuthUser) {
  sessionStorage.setItem("hostguard.user", JSON.stringify(user));
}

describe("UsersPage 用户管理", () => {
  beforeEach(() => {
    sessionStorage.clear();
    mocks.apiGet.mockResolvedValue({ items: users, page: 1, page_size: 20, total: 1 } satisfies Page<User>);
    mocks.apiPost.mockResolvedValue({ user: users[0] });
    mocks.apiPatch.mockResolvedValue({ user: users[0] });
    mocks.apiDelete.mockResolvedValue(undefined);
  });

  it("admin 可创建新用户", async () => {
    setUser(adminUser);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("zhang.yu")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "新增用户" }));
    const dialog = await screen.findByRole("dialog", { name: "新增用户" });

    fireEvent.change(within(dialog).getByPlaceholderText("zhang.san"), { target: { value: "chen.jie" } });
    fireEvent.change(within(dialog).getByPlaceholderText("user@example.com"), { target: { value: "chen@example.com" } });
    fireEvent.change(within(dialog).getByPlaceholderText("张三"), { target: { value: "陈杰" } });
    fireEvent.change(dialog.querySelector('input[type="password"]')!, { target: { value: "SecurePass123!" } });
    await user.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => {
      expect(mocks.apiPost).toHaveBeenCalledWith(
        "/users",
        expect.objectContaining({
          username: "chen.jie",
          email: "chen@example.com",
          role: "viewer",
        }),
      );
    });
  });

  it("搜索框触发带 search 参数的列表请求", async () => {
    setUser(adminUser);
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("zhang.yu");
    await user.type(screen.getByLabelText("搜索用户"), "zhang");

    await waitFor(() => {
      expect(mocks.apiGet).toHaveBeenCalledWith("/users", {
        query: expect.objectContaining({ search: "zhang" }),
      });
    });
  });
});
