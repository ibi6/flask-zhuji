// 审计日志页测试

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuditPage } from "@/pages/AuditPage";
import type { AuditEvent, Page } from "@/lib/types";

const mocks = vi.hoisted(() => ({ apiGet: vi.fn() }));

vi.mock("@/lib/api", () => ({
  apiGet: mocks.apiGet,
  apiPost: vi.fn(),
  apiPatch: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
  apiGetBlob: vi.fn(),
  isMockMode: () => false,
}));

const event: AuditEvent = {
  id: "e1",
  actor: "admin",
  action: "user.create",
  resource_type: "user",
  resource_id: "u1",
  outcome: "success",
  detail: "创建用户 chen.jie",
  occurred_at: "2026-07-01T00:00:00Z",
  ip: "10.0.0.2",
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuditPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AuditPage 审计日志", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.apiGet.mockResolvedValue({ items: [event], page: 1, page_size: 20, total: 1 } satisfies Page<AuditEvent>);
  });

  it("渲染审计记录", async () => {
    renderPage();
    expect(await screen.findByText("user.create")).toBeInTheDocument();
    expect(screen.getByText("创建用户 chen.jie")).toBeInTheDocument();
  });

  it("搜索时携带 q 参数", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("user.create");

    await user.type(screen.getByLabelText("搜索审计日志"), "admin");

    await waitFor(() => {
      expect(mocks.apiGet).toHaveBeenCalledWith("/audit", {
        query: expect.objectContaining({ q: "admin" }),
      });
    });
  });
});
