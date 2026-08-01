// 安全总览测试：真实 KPI（在线主机、告警分布、风险趋势）

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { OverviewPage } from "@/pages/OverviewPage";
import type { DashboardSummary } from "@/lib/types";

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

const summary: DashboardSummary = {
  hosts_total: 8,
  hosts_online: 6,
  hosts_degraded: 1,
  hosts_offline: 1,
  alerts_open: 3,
  alerts_critical: 2,
  alerts_high: 4,
  alerts_today: 8,
  events_today: 1243,
  rules_enabled: 6,
  alert_distribution: { critical: 2, high: 4, medium: 5, low: 3 },
  risk_trend: [
    { date: "07-18", critical: 1, high: 2, medium: 3, low: 2 },
    { date: "07-19", critical: 2, high: 1, medium: 4, low: 1 },
    { date: "07-20", critical: 0, high: 3, medium: 2, low: 2 },
  ],
  recent_alerts: [
    {
      id: "a1",
      host_id: "h1",
      hostname: "web-01",
      rule_id: "r1",
      rule_name: "异常登录",
      severity: "critical",
      status: "open",
      summary: "10 分钟内 12 次登录失败",
      details: null,
      occurred_at: "2026-07-20T00:00:00Z",
      updated_at: "2026-07-20T00:00:00Z",
      assignee: null,
    },
  ],
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <OverviewPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OverviewPage 真实 KPI", () => {
  it("渲染主机/告警 KPI 与告警分布", async () => {
    mocks.apiGet.mockResolvedValue(summary);
    renderPage();

    // 主机在线/降级/离线 KPI
    expect(await screen.findByText(/在线 6 · 降级 1 · 离线 1/)).toBeInTheDocument();
    // 未处理告警 KPI
    expect(screen.getByText(/严重 2 · 高危 4/)).toBeInTheDocument();
    // 告警分布使用真实分布计数（中危 5 条，数值唯一）
    expect(screen.getByText("5")).toBeInTheDocument();
    // 最近告警
    expect(screen.getByText("10 分钟内 12 次登录失败")).toBeInTheDocument();
  });

  it("渲染风险趋势图", async () => {
    mocks.apiGet.mockResolvedValue(summary);
    renderPage();

    const chart = await screen.findByRole("img", { name: "近 14 天风险趋势" });
    expect(chart).toBeInTheDocument();
  });
});
