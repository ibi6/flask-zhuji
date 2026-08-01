// 仪表盘外壳：flux-field 风格 glass sidebar + 顶栏 + 角色感知导航

import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  BellRing,
  Brain,
  Boxes,
  Bug,
  ChevronRight,
  FileText,
  Globe,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  Search,
  Server,
  Shield,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Link, Outlet, useNavigate } from "react-router-dom";
import { FluxScene } from "@/components/FluxScene";
import { ThemeToggle } from "@/components/ThemeToggle";
import { apiGet, isMockMode } from "@/lib/api";
import { useAuth } from "@/store/auth";
import type { Role } from "@/lib/types";

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  minRole: Role;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/overview", label: "安全总览", icon: LayoutDashboard, minRole: "viewer", end: true },
  { to: "/hosts", label: "主机管理", icon: Server, minRole: "viewer" },
  { to: "/assets", label: "资产中心", icon: Boxes, minRole: "viewer" },
  { to: "/alerts", label: "告警中心", icon: Bell, minRole: "viewer" },
  { to: "/vulnerabilities", label: "漏洞管理", icon: Bug, minRole: "viewer" },
  { to: "/rules", label: "检测规则", icon: ShieldCheck, minRole: "viewer" },
  { to: "/reports", label: "报告中心", icon: FileText, minRole: "analyst" },
  { to: "/threat-intel", label: "威胁情报", icon: Globe, minRole: "analyst" },
  { to: "/ai-analysis", label: "AI 分析", icon: Brain, minRole: "analyst" },
  { to: "/audit", label: "审计日志", icon: ScrollText, minRole: "viewer" },
  { to: "/notifications", label: "通知配置", icon: BellRing, minRole: "admin" },
  { to: "/users", label: "用户管理", icon: Users, minRole: "admin" },
];

const ROLE_ORDER: Role[] = ["viewer", "analyst", "admin"];

function canAccess(role: Role, minRole: Role): boolean {
  return ROLE_ORDER.indexOf(role) >= ROLE_ORDER.indexOf(minRole);
}

function useOpenAlertCount(): number {
  const { data } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => apiGet<{ alerts_open: number }>("/dashboard/summary"),
    staleTime: 30_000,
  });
  return data?.alerts_open ?? 0;
}

export function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [globalSearch, setGlobalSearch] = useState("");
  const openAlerts = useOpenAlertCount();
  const mock = isMockMode();

  if (!user) return null;

  const visibleItems = NAV_ITEMS.filter((item) => canAccess(user.role, item.minRole));

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b px-4 py-5" style={{ borderColor: "var(--divider)" }}>
        <div className="brand-mark shrink-0">
          <Shield className="h-7 w-7 text-[var(--accent)]" aria-hidden />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate font-[family-name:var(--font-display)] text-sm font-semibold tracking-tight">HostGuard</p>
            <p className="truncate text-[11px]" style={{ color: "var(--muted)" }}>
              主机安全态势感知
            </p>
          </div>
        )}
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-3" aria-label="主导航">
        {visibleItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMobileOpen(false)}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) => `nav-link ${isActive ? "is-active" : ""}`}
            >
              <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden />
              {!collapsed && <span className="truncate">{item.label}</span>}
              {!collapsed && item.to === "/alerts" && openAlerts > 0 && (
                <span
                  className="ml-auto min-w-[1.35rem] rounded-full px-1.5 py-0.5 text-center text-[10px] font-bold text-white"
                  style={{ background: "linear-gradient(135deg, var(--accent), var(--accent-deep))" }}
                >
                  {openAlerts}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>
      <div className="border-t px-4 py-3" style={{ borderColor: "var(--divider)" }}>
        <div className="flex items-center gap-3">
          <div
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
            style={{ background: "var(--sidebar-active)", color: "var(--accent)" }}
          >
            {user.display_name.slice(0, 1)}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{user.display_name}</p>
              <p className="truncate text-[11px]" style={{ color: "var(--muted)" }}>
                {user.username}
              </p>
            </div>
          )}
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-lg p-1.5 transition hover:bg-[var(--table-hover)]"
            style={{ color: "var(--muted)" }}
            title="退出登录"
            aria-label="退出登录"
          >
            <LogOut className="h-4 w-4" aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <FluxScene />
      <div className="app-shell flex h-screen overflow-hidden">
        <aside
          className={`glass-sidebar hidden shrink-0 transition-all duration-200 lg:block ${collapsed ? "w-[72px]" : "w-[16.5rem]"}`}
        >
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-end px-2 pt-3">
              <button
                type="button"
                onClick={() => setCollapsed((v) => !v)}
                className="rounded-lg p-1.5 transition hover:bg-[var(--table-hover)]"
                style={{ color: "var(--muted)" }}
                aria-label={collapsed ? "展开侧边栏" : "收起侧边栏"}
              >
                {collapsed ? <Menu className="h-4 w-4" /> : <X className="h-4 w-4" />}
              </button>
            </div>
            {sidebar}
          </div>
        </aside>

        {mobileOpen && (
          <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
            <aside className="glass-sidebar absolute inset-y-0 left-0 w-64 shadow-xl">{sidebar}</aside>
          </div>
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="glass-topbar flex h-14 shrink-0 items-center gap-3 px-4">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-lg p-1.5 lg:hidden"
              style={{ color: "var(--muted)" }}
              aria-label="打开菜单"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-1.5 text-sm" style={{ color: "var(--muted)" }}>
              <span className="hidden sm:inline">工作台</span>
              <ChevronRight className="hidden h-3.5 w-3.5 sm:inline" aria-hidden />
              <span className="font-semibold" style={{ color: "var(--ink)" }}>
                主机安全态势感知
              </span>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <form
                className="relative hidden md:block"
                onSubmit={(e) => {
                  e.preventDefault();
                  const q = globalSearch.trim();
                  if (q) navigate(`/hosts?q=${encodeURIComponent(q)}`);
                }}
              >
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: "var(--input-icon)" }} aria-hidden />
                <input
                  type="search"
                  value={globalSearch}
                  onChange={(e) => setGlobalSearch(e.target.value)}
                  placeholder="全局搜索主机/IP…"
                  className="input !w-44 !py-1.5 !pl-8 text-xs"
                  aria-label="全局搜索"
                />
              </form>
              <Link
                to="/alerts"
                className="relative flex h-9 w-9 items-center justify-center rounded-lg transition hover:bg-[var(--table-hover)]"
                style={{ color: "var(--muted)" }}
                title="通知中心"
                aria-label={`告警中心${openAlerts > 0 ? `，${openAlerts} 条未处理` : ""}`}
              >
                <BellRing className="h-4 w-4" aria-hidden />
                {openAlerts > 0 && (
                  <span
                    className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full px-1 text-[9px] font-bold text-white"
                    style={{ background: "var(--danger)" }}
                  >
                    {openAlerts > 9 ? "9+" : openAlerts}
                  </span>
                )}
              </Link>
              {mock && (
                <span
                  className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium"
                  style={{ background: "rgba(251, 191, 36, 0.12)", color: "var(--warning)", border: "1px solid rgba(251, 191, 36, 0.25)" }}
                  title="VITE_USE_MOCK 开启，数据为本地模拟"
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden />
                  开发模式
                </span>
              )}
              <span className="hidden text-xs sm:inline" style={{ color: "var(--muted)" }}>
                角色：
                <span className="font-medium" style={{ color: "var(--ink-soft)" }}>
                  {user.role === "admin" ? "管理员" : user.role === "analyst" ? "分析员" : "只读用户"}
                </span>
              </span>
              <ThemeToggle />
            </div>
          </header>
          <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
            <Outlet />
          </main>
        </div>
      </div>
    </>
  );
}
