// 登录页 — flux-field 玻璃拟态 + 多角色快捷登录

import { Eye, Lock, Shield, ShieldCheck, User, UserCog } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { FormEvent } from "react";
import { FluxScene } from "@/components/FluxScene";
import { ThemeToggle } from "@/components/ThemeToggle";
import { isMockMode } from "@/lib/api";
import { useAuth } from "@/store/auth";
import type { Role } from "@/lib/types";

interface DemoAccount {
  role: Role;
  username: string;
  password: string;
  displayName: string;
  title: string;
  description: string;
  permissions: string[];
  icon: typeof Shield;
  iconClass: string;
}

const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    role: "admin",
    username: "admin",
    password: "AdminPass123!",
    displayName: "安全管理员",
    title: "管理员",
    description: "系统配置、用户与通知管理，拥有全部权限",
    permissions: ["用户管理", "通知配置", "规则编辑", "报告导出"],
    icon: ShieldCheck,
    iconClass: "role-icon--admin",
  },
  {
    role: "analyst",
    username: "analyst",
    password: "AnalystPass123!",
    displayName: "安全分析员",
    title: "分析员",
    description: "调查告警、创建与下载安全报告",
    permissions: ["告警处置", "报告中心", "主机详情", "规则查看"],
    icon: UserCog,
    iconClass: "role-icon--analyst",
  },
  {
    role: "viewer",
    username: "viewer",
    password: "ViewerPass123!",
    displayName: "只读观察员",
    title: "只读用户",
    description: "查看仪表盘、主机、告警与审计，不可变更配置",
    permissions: ["安全总览", "主机列表", "告警查看", "审计只读"],
    icon: Eye,
    iconClass: "role-icon--viewer",
  },
];

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const mock = isMockMode();

  const from = (location.state as { from?: string } | null)?.from ?? "/overview";

  const performLogin = async (user: string, pass: string) => {
    setError(null);
    setSubmitting(true);
    try {
      await login(user.trim(), pass);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError("请输入用户名和密码");
      return;
    }
    await performLogin(username.trim(), password);
  };

  const handleRoleSelect = (account: DemoAccount) => {
    setSelectedRole(account.role);
    setUsername(account.username);
    setPassword(account.password);
    setError(null);
  };

  const handleRoleLogin = async (account: DemoAccount) => {
    handleRoleSelect(account);
    await performLogin(account.username, account.password);
  };

  return (
    <>
      <FluxScene />
      <div className="auth-layout">
        <div className="fixed right-4 top-4 z-10 sm:right-6 sm:top-6">
          <ThemeToggle />
        </div>

        <div className="auth-card-wrap auth-card-wrap--wide">
          <div className="auth-card-glow" aria-hidden />
          <div className="auth-card p-6 sm:p-8">
            <div className="auth-card-accent" aria-hidden />

            <div className="mb-6 text-center">
              <div className="brand-mark mx-auto mb-3">
                <Shield className="h-8 w-8 text-[var(--accent)]" aria-hidden />
              </div>
              <p className="mb-2 font-[family-name:var(--font-mono)] text-[0.65rem] uppercase tracking-[0.22em]" style={{ color: "var(--muted)" }}>
                HostGuard Platform
              </p>
              <h1 className="auth-title">
                <span className="title-gradient">安全登录</span>
              </h1>
              <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
                选择角色体验不同权限，或使用账号密码登录
              </p>
            </div>

            {/* 角色快捷入口 */}
            <div className="mb-5">
              <p className="mb-2.5 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--muted)" }}>
                演示角色 · 一键登录
              </p>
              <div className="role-grid" role="group" aria-label="演示角色选择">
                {DEMO_ACCOUNTS.map((account) => {
                  const Icon = account.icon;
                  const isSelected = selectedRole === account.role;
                  return (
                    <button
                      key={account.role}
                      type="button"
                      disabled={submitting}
                      onClick={() => handleRoleLogin(account)}
                      className={`role-card ${isSelected ? "is-selected" : ""}`}
                      aria-pressed={isSelected}
                      aria-label={`以${account.title}身份登录：${account.description}`}
                    >
                      <div className={`role-icon ${account.iconClass}`}>
                        <Icon className="h-4 w-4" aria-hidden />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-semibold" style={{ color: "var(--ink)" }}>
                            {account.title}
                          </p>
                          <span className="font-mono text-[10px]" style={{ color: "var(--muted)" }}>
                            {account.username}
                          </span>
                        </div>
                        <p className="mt-0.5 text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
                          {account.description}
                        </p>
                        <div className="role-perms">
                          {account.permissions.map((perm) => (
                            <span key={perm} className="role-perm">
                              {perm}
                            </span>
                          ))}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="mb-4 flex items-center gap-3">
              <div className="h-px flex-1" style={{ background: "var(--divider)" }} />
              <span className="text-[11px]" style={{ color: "var(--muted)" }}>
                或手动登录
              </span>
              <div className="h-px flex-1" style={{ background: "var(--divider)" }} />
            </div>

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              {mock && (
                <p
                  className="rounded-xl px-3 py-2 text-xs ring-1"
                  style={{ background: "rgba(251, 191, 36, 0.1)", color: "var(--warning)", borderColor: "rgba(251, 191, 36, 0.25)" }}
                  role="status"
                >
                  开发模式：点击上方角色卡片可一键登录；手动输入时{" "}
                  <span className="font-mono">admin</span> / <span className="font-mono">analyst</span> /{" "}
                  <span className="font-mono">viewer</span> 对应不同角色，任意密码均可。
                </p>
              )}

              <div>
                <label htmlFor="username" className="mb-1.5 block text-sm font-medium" style={{ color: "var(--ink-soft)" }}>
                  用户名
                </label>
                <div className="relative">
                  <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: "var(--input-icon)" }} aria-hidden />
                  <input
                    id="username"
                    className="input !pl-10"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => {
                      setUsername(e.target.value);
                      setSelectedRole(null);
                    }}
                    placeholder="admin / analyst / viewer"
                    disabled={submitting}
                  />
                </div>
              </div>

              <div>
                <label htmlFor="password" className="mb-1.5 block text-sm font-medium" style={{ color: "var(--ink-soft)" }}>
                  密码
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: "var(--input-icon)" }} aria-hidden />
                  <input
                    id="password"
                    type="password"
                    className="input !pl-10"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="请输入密码"
                    disabled={submitting}
                  />
                </div>
              </div>

              {error && (
                <p
                  className="rounded-xl px-3 py-2 text-xs ring-1"
                  style={{ background: "rgba(248, 113, 113, 0.1)", color: "var(--danger)", borderColor: "rgba(248, 113, 113, 0.25)" }}
                  role="alert"
                >
                  {error}
                </p>
              )}

              <button type="submit" className="btn-primary w-full !py-2.5" disabled={submitting}>
                {submitting ? "登录中…" : "登 录"}
              </button>
            </form>
          </div>

          <p className="mt-6 text-center text-xs" style={{ color: "var(--muted)" }}>
            HostGuard v0.1 · 仅限授权人员访问，所有操作将被审计记录
          </p>
        </div>
      </div>
    </>
  );
}
