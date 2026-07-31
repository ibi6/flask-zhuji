// 登录页

import { Shield } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { FormEvent } from "react";
import { isMockMode } from "@/lib/api";
import { useAuth } from "@/store/auth";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const mock = isMockMode();

  const from = (location.state as { from?: string } | null)?.from ?? "/overview";

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!username.trim() || !password) {
      setError("请输入用户名和密码");
      return;
    }
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas-100 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-600 shadow-pop">
            <Shield className="h-6 w-6 text-white" aria-hidden />
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">HostGuard</h1>
          <p className="text-sm text-slate-500">主机安全态势感知平台</p>
        </div>

        <form onSubmit={handleSubmit} className="card space-y-4 p-6" noValidate>
          {mock && (
            <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700 ring-1 ring-amber-200" role="status">
              开发模式：使用任意用户名/密码登录，<span className="font-mono">admin</span> 为管理员账号。
            </p>
          )}
          <div>
            <label htmlFor="username" className="mb-1.5 block text-sm font-medium text-slate-700">
              用户名
            </label>
            <input
              id="username"
              className="input"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
              disabled={submitting}
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-700">
              密码
            </label>
            <input
              id="password"
              type="password"
              className="input"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              disabled={submitting}
            />
          </div>
          {error && (
            <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700 ring-1 ring-rose-200" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="btn-primary w-full" disabled={submitting}>
            {submitting ? "登录中…" : "登 录"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-400">
          HostGuard v0.1 · 仅限授权人员访问，所有操作将被审计记录
        </p>
      </div>
    </div>
  );
}
