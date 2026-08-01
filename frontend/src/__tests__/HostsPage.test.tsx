// 主机列表页测试

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HostsPage } from "@/pages/HostsPage";
import type { Host, Page } from "@/lib/types";

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

const host: Host = {
  id: "h1",
  hostname: "web-prod-01",
  os: "linux",
  os_version: "22.04",
  architecture: "x86_64",
  status: "online",
  source: "real",
  ip_addresses: ["10.0.0.10"],
  agent_version: "1.0.0",
  last_seen_at: "2026-07-01T00:00:00Z",
  created_at: "2026-01-01T00:00:00Z",
  metrics: {
    cpu_percent: 42,
    memory_percent: 55,
    disk_percent: 60,
    network_bytes_sent: 0,
    network_bytes_recv: 0,
    collected_at: "2026-07-01T00:00:00Z",
  },
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <HostsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("HostsPage 主机管理", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.apiGet.mockResolvedValue({ items: [host], page: 1, page_size: 10, total: 1 } satisfies Page<Host>);
  });

  it("默认卡片视图渲染主机信息", async () => {
    renderPage();
    expect(await screen.findByText("web-prod-01")).toBeInTheDocument();
    expect(screen.getByText(/linux · 22\.04/)).toBeInTheDocument();
  });

  it("可切换到列表视图", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("web-prod-01");

    await user.click(screen.getByRole("button", { name: "列表" }));
    expect(screen.getByRole("table")).toBeInTheDocument();
  });
});
