// 安全总览测试：SOC Dashboard KPI

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
  security_score: 78,
  attack_events: 156,
  attack_trend_24h: [{ hour: "08:00", count: 5 }],
  attack_types: [{ name: "SSH 爆破", count: 10 }],
  top_attack_ips: [{ label: "1.2.3.4", value: 20, meta: "测试" }],
  ai_insight: {
    summary: "测试 AI 分析摘要",
    risk_level: "high",
    recommendations: ["建议一"],
  },
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

describe("OverviewPage SOC Dashboard", () => {
  it("渲染核心 KPI 与 AI 分析", async () => {
    mocks.apiGet.mockResolvedValue(summary);
    renderPage();

    expect(await screen.findByText("安全态势总览")).toBeInTheDocument();
    expect(await screen.findByText(/在线 6/)).toBeInTheDocument();
    expect(await screen.findByText("攻击事件")).toBeInTheDocument();
    expect(await screen.findByText("测试 AI 分析摘要")).toBeInTheDocument();
    expect(await screen.findByText("10 分钟内 12 次登录失败")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /详情/ })).toBeInTheDocument();
  });

  it("渲染风险趋势图", async () => {
    mocks.apiGet.mockResolvedValue(summary);
    renderPage();

    const chart = await screen.findByRole("img", { name: "近 14 天风险趋势" });
    expect(chart).toBeInTheDocument();
  });
});
