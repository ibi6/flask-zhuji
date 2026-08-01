// 规则管理测试：admin 可新建规则，analyst/viewer 只读

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RulesPage } from "@/pages/RulesPage";
import { AuthProvider, type AuthUser } from "@/store/auth";
import type { DetectionRule } from "@/lib/types";

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPatch: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiGet: mocks.apiGet,
  apiPost: mocks.apiPost,
  apiPatch: mocks.apiPatch,
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
  apiGetBlob: vi.fn(),
  isMockMode: () => true,
  refreshCsrf: vi.fn(async () => undefined),
}));

const rules: DetectionRule[] = [
  {
    id: "r1",
    name: "CPU 持续高负载",
    description: "CPU 超过 85%",
    severity: "high",
    enabled: true,
    kind: "metric",
    condition_field: "cpu_percent",
    condition_op: ">=",
    window_seconds: 300,
    threshold: 85,
    updated_at: "2026-07-01T00:00:00Z",
  },
];

const adminUser: AuthUser = { id: "u-admin", username: "admin", display_name: "管理员", role: "admin" };
const viewerUser: AuthUser = { id: "u-viewer", username: "viewer", display_name: "访客", role: "viewer" };

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuthProvider>
          <RulesPage />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function setUser(user: AuthUser) {
  sessionStorage.setItem("hostguard.user", JSON.stringify(user));
}

describe("RulesPage 规则管理", () => {
  beforeEach(() => {
    sessionStorage.clear();
    mocks.apiGet.mockResolvedValue(rules);
    mocks.apiPost.mockResolvedValue(rules[0]);
    mocks.apiPatch.mockResolvedValue(rules[0]);
  });

  it("admin 可打开规则编辑器并创建新规则", async () => {
    setUser(adminUser);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("CPU 持续高负载")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "新建规则" }));
    const dialog = await screen.findByRole("dialog", { name: "新建规则" });
    expect(dialog).toBeInTheDocument();

    await user.type(screen.getByLabelText("规则名称"), "异常外联检测");
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(mocks.apiPost).toHaveBeenCalledWith(
        "/rules",
        expect.objectContaining({ name: "异常外联检测", severity: "medium", enabled: true }),
      );
    });
  });

  it("viewer 角色为只读，不显示新建与编辑按钮", async () => {
    setUser(viewerUser);
    renderPage();

    expect(await screen.findByText("CPU 持续高负载")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "新建规则" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "编辑" })).not.toBeInTheDocument();
    expect(screen.getByText(/当前角色无修改权限/)).toBeInTheDocument();
  });
});
