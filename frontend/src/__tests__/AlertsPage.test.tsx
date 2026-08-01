// 告警处置工作流测试：单条/批量状态流转、详情状态历史

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AlertsPage } from "@/pages/AlertsPage";
import type { Alert, AlertDetail } from "@/lib/types";

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiGet: mocks.apiGet,
  apiPost: mocks.apiPost,
  apiPatch: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
  apiGetBlob: vi.fn(),
  isMockMode: () => false,
}));

vi.mock("@/lib/exportCsv", () => ({
  downloadCsv: vi.fn(),
}));

import { downloadCsv } from "@/lib/exportCsv";

const openAlert: Alert = {
  id: "a1",
  host_id: "h1",
  hostname: "web-01",
  rule_id: "r1",
  rule_name: "CPU 高负载",
  severity: "high",
  status: "open",
  summary: "CPU 使用率持续过高",
  details: "峰值 92%",
  occurred_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z",
  assignee: null,
};

const investigatingAlert: Alert = {
  id: "a2",
  host_id: "h2",
  hostname: "db-01",
  rule_id: "r2",
  rule_name: "内存告警",
  severity: "critical",
  status: "investigating",
  summary: "内存使用率接近阈值",
  details: null,
  occurred_at: "2026-07-01T00:30:00Z",
  updated_at: "2026-07-01T00:40:00Z",
  assignee: "li.wei",
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AlertsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AlertsPage 告警处置工作流", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("列表渲染告警并支持单条状态流转", async () => {
    mocks.apiGet.mockImplementation((path: string) => {
      if (path === "/alerts") {
        return Promise.resolve({ items: [openAlert, investigatingAlert], page: 1, page_size: 15, total: 2 });
      }
      return Promise.resolve(openAlert);
    });
    mocks.apiPost.mockResolvedValue({ ...openAlert, status: "resolved" });

    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("CPU 使用率持续过高")).toBeInTheDocument();
    expect(screen.getByText("内存使用率接近阈值")).toBeInTheDocument();

    // 打开单条处置弹窗
    await user.click(screen.getAllByRole("button", { name: "处置" })[0]!);
    expect(await screen.findByRole("dialog", { name: "处置告警" })).toBeInTheDocument();

    // 选择目标状态并确认
    await user.click(screen.getByRole("radio", { name: "已解决" }));
    await user.click(screen.getByRole("button", { name: "确认处置" }));

    await waitFor(() => {
      expect(mocks.apiPost).toHaveBeenCalledWith("/alerts/a1/transitions", { to_status: "resolved", comment: undefined });
    });
  });

  it("支持批量状态流转并调用每个告警的 transitions 端点", async () => {
    mocks.apiGet.mockResolvedValue({ items: [openAlert, investigatingAlert], page: 1, page_size: 15, total: 2 });
    mocks.apiPost.mockResolvedValue(openAlert);

    const user = userEvent.setup();
    renderPage();

    await screen.findByText("CPU 使用率持续过高");

    // 勾选当前页全部告警
    await user.click(screen.getByLabelText("选择当前页全部告警"));
    await user.click(screen.getByRole("button", { name: /批量处置/ }));

    const dialog = await screen.findByRole("dialog", { name: "批量处置（2 条告警）" });
    expect(dialog).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "已忽略" }));
    await user.click(screen.getByRole("button", { name: "确认处置" }));

    await waitFor(() => {
      expect(mocks.apiPost).toHaveBeenCalledTimes(2);
      expect(mocks.apiPost).toHaveBeenCalledWith("/alerts/a1/transitions", { to_status: "ignored", comment: undefined });
      expect(mocks.apiPost).toHaveBeenCalledWith("/alerts/a2/transitions", { to_status: "ignored", comment: undefined });
    });
  });

  it("详情弹窗展示状态历史", async () => {
    const detail: AlertDetail = {
      ...openAlert,
      status: "resolved",
      transitions: [
        { id: "t1", from_status: "open", to_status: "investigating", comment: "开始排查", actor: "li.wei", occurred_at: "2026-07-01T00:10:00Z" },
        { id: "t2", from_status: "investigating", to_status: "resolved", comment: "已确认为计划内变更", actor: "li.wei", occurred_at: "2026-07-01T00:20:00Z" },
      ],
    };
    mocks.apiGet.mockImplementation((path: string) => {
      if (path === "/alerts") {
        return Promise.resolve({ items: [openAlert, investigatingAlert], page: 1, page_size: 15, total: 2 });
      }
      return Promise.resolve(detail);
    });

    const user = userEvent.setup();
    renderPage();

    await screen.findByText("CPU 使用率持续过高");
    await user.click(screen.getAllByRole("button", { name: "详情" })[0]!);

    expect(await screen.findByRole("dialog", { name: "告警详情" })).toBeInTheDocument();
    expect(screen.getByText("状态历史")).toBeInTheDocument();
    expect(await screen.findByText(/已确认为计划内变更/)).toBeInTheDocument();
  });

  it("导出 Excel 按当前筛选拉取告警并下载 CSV", async () => {
    mocks.apiGet.mockResolvedValue({ items: [openAlert], page: 1, page_size: 500, total: 1 });

    const user = userEvent.setup();
    renderPage();

    await screen.findByText("CPU 使用率持续过高");
    await user.click(screen.getByRole("button", { name: "导出 Excel" }));

    await waitFor(() => {
      expect(mocks.apiGet).toHaveBeenCalledWith("/alerts", {
        query: { page: 1, page_size: 500, severity: undefined, status: undefined },
      });
      expect(downloadCsv).toHaveBeenCalled();
    });
  });
});
