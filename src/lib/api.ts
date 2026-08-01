// API 客户端：同源凭据、CSRF、结构化错误，与 contracts/conventions.md 对齐
// mock 分支仅在 VITE_USE_MOCK === "true" 时激活，默认走真实 API。

import { handleMock, MOCK_ACTIVE } from "./mock";
import type { ErrorEnvelope } from "./types";

export const API_PREFIX = "/api/v1";

/** 当前是否处于开发 mock 模式（界面需显式标注，不得伪装为真实数据） */
export const isMockMode = (): boolean => MOCK_ACTIVE;

export class ApiError extends Error {
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly requestId: string;
  readonly status: number;

  constructor(envelope: ErrorEnvelope, status: number) {
    super(envelope.error.message);
    this.name = "ApiError";
    this.code = envelope.error.code;
    this.details = envelope.error.details ?? {};
    this.requestId = envelope.error.request_id;
    this.status = status;
  }
}

/** 从响应体中尽力解析错误信封 */
async function parseEnvelope(res: Response): Promise<ErrorEnvelope> {
  try {
    const body = (await res.json()) as ErrorEnvelope;
    if (body && body.error && typeof body.error.code === "string") return body;
  } catch {
    // 非 JSON 响应
  }
  return {
    error: {
      code: `http_${res.status}`,
      message: res.statusText || `请求失败（HTTP ${res.status}）`,
      request_id: "00000000-0000-0000-0000-000000000000",
    },
  };
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(API_PREFIX + path, window.location.origin);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/** 构造传给 mock 适配器的查询参数 */
function toSearchParams(query?: RequestOptions["query"]): URLSearchParams {
  const q = new URLSearchParams();
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) q.set(key, String(value));
    }
  }
  return q;
}

async function mockInvoke<T>(path: string, options: RequestOptions): Promise<T> {
  const result = await handleMock({
    method: options.method ?? "GET",
    path,
    params: toSearchParams(options.query),
    body: options.body,
  });
  return result as T;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  // 开发 mock 模式：走本地适配器，不发出真实网络请求
  if (MOCK_ACTIVE) {
    return mockInvoke<T>(path, options);
  }
  const res = await rawRequest(path, options);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** 底层 fetch，统一错误信封解析（仅真实 API 模式使用） */
async function rawRequest(path: string, options: RequestOptions = {}): Promise<Response> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
    ...options.headers,
  };

  // 变更请求附带 CSRF token（真实后端：/auth/csrf 返回后写入 header）
  if (options.method && options.method !== "GET") {
    const csrf = getCsrfToken();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }

  const res = await fetch(buildUrl(path, options.query), {
    method: options.method ?? "GET",
    credentials: "same-origin",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  });

  if (!res.ok) {
    const envelope = await parseEnvelope(res);
    throw new ApiError(envelope, res.status);
  }
  return res;
}

// ---- CSRF 处理 ----

const CSRF_KEY = "hostguard.csrf";

/** 获取 CSRF token：优先内存/缓存，其次从服务端获取 */
export function getCsrfToken(): string | null {
  return window.sessionStorage.getItem(CSRF_KEY);
}

export function setCsrfToken(token: string): void {
  window.sessionStorage.setItem(CSRF_KEY, token);
}

export function clearCsrfToken(): void {
  window.sessionStorage.removeItem(CSRF_KEY);
}

/** 显式刷新 CSRF token（登录前调用） */
export async function refreshCsrf(): Promise<void> {
  if (MOCK_ACTIVE) {
    const data = await mockInvoke<{ token: string }>("/auth/csrf", { method: "GET" });
    setCsrfToken(data.token);
    return;
  }
  const res = await rawRequest("/auth/csrf", { method: "GET" });
  const data = (await res.json()) as { token: string };
  setCsrfToken(data.token);
}

// ---- 认证 ----

export interface CurrentUser {
  id: string;
  username: string;
  display_name: string;
  role: "admin" | "analyst" | "viewer";
}

export const apiGet = <T>(path: string, options?: RequestOptions) =>
  request<T>(path, options);

export const apiPost = <T>(path: string, body?: unknown, options?: RequestOptions) =>
  request<T>(path, { ...options, method: "POST", body });

export const apiPut = <T>(path: string, body?: unknown, options?: RequestOptions) =>
  request<T>(path, { ...options, method: "PUT", body });

export const apiPatch = <T>(path: string, body?: unknown, options?: RequestOptions) =>
  request<T>(path, { ...options, method: "PATCH", body });

export const apiDelete = <T>(path: string, options?: RequestOptions) =>
  request<T>(path, { ...options, method: "DELETE" });

/** 以二进制方式下载文件（报告下载等） */
export async function apiGetBlob(path: string, options?: RequestOptions): Promise<Blob> {
  if (MOCK_ACTIVE) {
    return mockInvoke<Blob>(path, { ...options, method: "GET" });
  }
  const res = await rawRequest(path, options);
  return res.blob();
}

export const api = {
  get: apiGet,
  post: apiPost,
  put: apiPut,
  patch: apiPatch,
  delete: apiDelete,
};
