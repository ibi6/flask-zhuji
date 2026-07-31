// API 客户端：同源凭据、CSRF、结构化错误，与 contracts/conventions.md 对齐

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

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  // 开发 mock 模式：走本地适配器，不发出真实网络请求
  if (MOCK_ACTIVE) {
    const query = new URLSearchParams();
    if (options.query) {
      for (const [key, value] of Object.entries(options.query)) {
        if (value !== undefined) query.set(key, String(value));
      }
    }
    return (await handleMock({
      method: options.method ?? "GET",
      path,
      params: query,
    })) as T;
  }

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

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
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
  const data = await request<{ token: string }>("/auth/csrf");
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

export const apiPatch = <T>(path: string, body?: unknown, options?: RequestOptions) =>
  request<T>(path, { ...options, method: "PATCH", body });

export const apiDelete = <T>(path: string, options?: RequestOptions) =>
  request<T>(path, { ...options, method: "DELETE" });

export const api = {
  get: apiGet,
  post: apiPost,
  patch: apiPatch,
  delete: apiDelete,
};
