// 新模块页面渲染与交互测试

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AiAnalysisPage } from "@/pages/AiAnalysisPage";
import { AssetsPage } from "@/pages/AssetsPage";
import { ThreatIntelPage } from "@/pages/ThreatIntelPage";
import { VulnerabilitiesPage } from "@/pages/VulnerabilitiesPage";
import type { AiAnalysisReport, AssetRecord, Page, ThreatIndicator, Vulnerability } from "@/lib/types";

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPatch: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiGet: mocks.apiGet,
  apiPatch: mocks.apiPatch,
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
  apiGetBlob: vi.fn(),
  isMockMode: () => false,
}));

const vuln: Vulnerability = {
  id: "v1",
  cve_id: "CVE-2024-0001",
  title: "测试漏洞",
  severity: "high",
  fix_status: "open",
  host_id: "h1",
  hostname: "web-01",
  cvss_score: 8.5,
  published_at: "2026-01-01T00:00:00Z",
  discovered_at: "2026-02-01T00:00:00Z",
};

const asset: AssetRecord = {
  id: "h1",
  hostname: "web-01",
  os: "Ubuntu",
  os_version: "22.04",
  tags: ["生产"],
  status: "online",
  ip_addresses: ["10.0.0.1"],
  agent_version: "1.2.0",
  last_seen_at: "2026-07-01T00:00:00Z",
  department: "运维部",
};

const indicator: ThreatIndicator = {
  id: "t1",
  ioc_type: "ip",
  value: "203.0.113.1",
  threat_type: "扫描",
  confidence: 90,
  source: "蜜罐",
  first_seen: "2026-06-01T00:00:00Z",
  last_seen: "2026-07-01T00:00:00Z",
  blocked: false,
};

const aiReport: AiAnalysisReport = {
  id: "ai1",
  title: "测试 AI 报告",
  generated_at: "2026-07-01T00:00:00Z",
  risk_score: 80,
  risk_level: "high",
  summary: "这是一条测试 AI 摘要",
  attack_chain: ["扫描", "爆破"],
  affected_hosts: ["web-01"],
  recommendations: ["封禁 IP"],
  related_alert_count: 2,
};

function renderPage(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("新模块页面", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("VulnerabilitiesPage 渲染 CVE 并支持状态更新", async () => {
    mocks.apiGet.mockResolvedValue({ items: [vuln], page: 1, page_size: 10, total: 1 } satisfies Page<Vulnerability>);
    mocks.apiPatch.mockResolvedValue({ ...vuln, fix_status: "fixed" });

    const user = userEvent.setup();
    renderPage(<VulnerabilitiesPage />);

    expect(await screen.findByText("CVE-2024-0001")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText(`更新 ${vuln.cve_id} 修复状态`), "fixed");

    await waitFor(() => {
      expect(mocks.apiPatch).toHaveBeenCalledWith("/vulnerabilities/v1", { fix_status: "fixed" });
    });
  });

  it("AssetsPage 渲染资产卡片", async () => {
    mocks.apiGet.mockResolvedValue({ items: [asset], page: 1, page_size: 12, total: 1 } satisfies Page<AssetRecord>);
    renderPage(<AssetsPage />);

    expect(await screen.findByText("web-01")).toBeInTheDocument();
    expect(screen.getByText("运维部")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /web-01/ })).toHaveAttribute("href", "/hosts/h1");
  });

  it("ThreatIntelPage 支持封禁 IOC", async () => {
    mocks.apiGet.mockResolvedValue({ items: [indicator], page: 1, page_size: 10, total: 1 } satisfies Page<ThreatIndicator>);
    mocks.apiPatch.mockResolvedValue({ ...indicator, blocked: true });

    const user = userEvent.setup();
    renderPage(<ThreatIntelPage />);

    expect(await screen.findByText("203.0.113.1")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "封禁" }));

    await waitFor(() => {
      expect(mocks.apiPatch).toHaveBeenCalledWith("/threat-intel/t1", { blocked: true });
    });
  });

  it("AiAnalysisPage 打开详情弹窗", async () => {
    mocks.apiGet.mockImplementation((path: string) => {
      if (path === "/ai-analysis") {
        return Promise.resolve({ items: [aiReport], page: 1, page_size: 6, total: 1 });
      }
      return Promise.resolve(aiReport);
    });

    const user = userEvent.setup();
    renderPage(<AiAnalysisPage />);

    expect(await screen.findByText("测试 AI 报告")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /测试 AI 报告/ }));

    expect(await screen.findByRole("dialog", { name: "测试 AI 报告" })).toBeInTheDocument();
    expect(screen.getByText("封禁 IP")).toBeInTheDocument();
  });
});
