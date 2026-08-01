// Mock 新模块端点测试

import { describe, expect, it } from "vitest";
import { handleMock, mockAiReports, mockThreatIndicators, mockVulnerabilities } from "@/lib/mock";

function ctx(path: string, params: Record<string, string> = {}, method = "GET", body?: unknown) {
  return {
    path,
    method,
    params: new URLSearchParams(params),
    body,
  };
}

describe("handleMock 新模块 API", () => {
  it("GET /vulnerabilities 支持分页与筛选", async () => {
    const page = (await handleMock(ctx("/vulnerabilities", { page: "1", page_size: "3" }))) as {
      items: unknown[];
      total: number;
    };
    expect(page.items).toHaveLength(3);
    expect(page.total).toBe(mockVulnerabilities.length);

    const critical = (await handleMock(ctx("/vulnerabilities", { severity: "critical", page_size: "10" }))) as {
      items: { severity: string }[];
    };
    expect(critical.items.every((v) => v.severity === "critical")).toBe(true);
  });

  it("PATCH /vulnerabilities/{id} 更新修复状态", async () => {
    const target = mockVulnerabilities[0]!;
    const before = target.fix_status;
    const updated = (await handleMock(
      ctx(`/vulnerabilities/${target.id}`, {}, "PATCH", { fix_status: "fixed" }),
    )) as { fix_status: string };
    expect(updated.fix_status).toBe("fixed");
    target.fix_status = before;
  });

  it("GET /assets 支持搜索", async () => {
    const result = (await handleMock(ctx("/assets", { search: "mysql", page_size: "10" }))) as {
      items: { hostname: string }[];
    };
    expect(result.items.length).toBeGreaterThan(0);
    expect(result.items.some((a) => a.hostname.includes("mysql"))).toBe(true);
  });

  it("GET /threat-intel 与 PATCH 封禁", async () => {
    const list = (await handleMock(ctx("/threat-intel", { page_size: "10" }))) as { items: unknown[] };
    expect(list.items.length).toBeGreaterThan(0);

    const target = mockThreatIndicators.find((t) => !t.blocked)!;
    const updated = (await handleMock(
      ctx(`/threat-intel/${target.id}`, {}, "PATCH", { blocked: true }),
    )) as { blocked: boolean };
    expect(updated.blocked).toBe(true);
    target.blocked = false;
  });

  it("GET /ai-analysis 列表与详情", async () => {
    const list = (await handleMock(ctx("/ai-analysis", { page_size: "5" }))) as { items: unknown[] };
    expect(list.items.length).toBeGreaterThan(0);

    const report = (await handleMock(ctx(`/ai-analysis/${mockAiReports[0]!.id}`))) as { title: string };
    expect(report.title).toBe(mockAiReports[0]!.title);
  });
});
