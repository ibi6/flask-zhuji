// API 客户端错误处理测试

import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiGet } from "@/lib/api";
import type { ErrorEnvelope } from "@/lib/types";

// 关闭 mock 模式，让 apiGet 走真实 fetch 分支
vi.mock("@/lib/mock", () => ({
  MOCK_ACTIVE: false,
  handleMock: vi.fn(),
}));

const envelope: ErrorEnvelope = {
  error: {
    code: "UNAUTHORIZED",
    message: "认证已过期，请重新登录",
    request_id: "req-123",
  },
};

function mockResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    statusText: status === 401 ? "Unauthorized" : "Error",
    headers: { "Content-Type": "application/json" },
  });
}

describe("API 客户端错误处理", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("401 响应抛出 ApiError 并携带错误信封信息", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockResponse(401, envelope));

    await expect(apiGet("/hosts")).rejects.toMatchObject({
      name: "ApiError",
      code: "UNAUTHORIZED",
      status: 401,
      requestId: "req-123",
    });
  });

  it("ApiError 的 message 来自信封", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockResponse(401, envelope));

    await expect(apiGet("/alerts")).rejects.toThrow("认证已过期，请重新登录");
  });

  it("非 JSON 响应时生成兜底错误", async () => {
    const res = new Response("Internal Server Error", { status: 500, statusText: "Internal Server Error" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(res);

    const err = (await apiGet("/dashboard/summary").catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(500);
    expect(err.code).toBe("http_500");
  });

  it("成功响应返回解析后的 JSON", async () => {
    const data = { hosts_total: 8 };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } }),
    );

    await expect(apiGet("/dashboard/summary")).resolves.toEqual(data);
  });
});
