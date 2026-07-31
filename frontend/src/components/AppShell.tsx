// 仪表盘外壳：可折叠侧边栏 + 顶栏 + 角色感知导航

import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  BellRing,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  Server,
  Shield,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
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
  { to: "/alerts", label: "告警中心", icon: Bell, minRole: "viewer" },
  { to: "/rules", label: "检测规则", icon: ShieldCheck, minRole: "viewer" },
  { to: "/reports", label: "报告中心", icon: FileText, minRole: "analyst" },
  { to: "/notifications", label: "通知配置", icon: BellRing, minRole: "admin" },
  { to: "/users", label: "用户管理", icon: Users, minRole: "admin" },
  { to: "/audit", label: "审计日志", icon: ScrollText, minRole: "admin" },
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
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 shadow-sm">
          <Shield className="h-5 w-5 text-white" aria-hidden />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight text-slate-900">HostGuard</p>
            <p className="truncate text-[11px] text-slate-400">主机安全态势感知平台</p>
          </div>
        )}
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3" aria-label="主导航">
        {visibleItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMobileOpen(false)}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? "bg-brand-50 text-brand-700 shadow-sm ring-1 ring-brand-100"
                    : "text-slate-600 hover:bg-white hover:text-slate-900 hover:shadow-card"
                }`
              }
            >
              <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden />
              {!collapsed && <span className="truncate">{item.label}</span>}
              {!collapsed && item.to === "/alerts" && openAlerts > 0 && (
                <span className="ml-auto rounded-full bg-rose-100 px-1.5 py-0.5 text-[10px] font-semibold text-rose-700">
                  {openAlerts}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>
      <div className="border-t border-slate-200/70 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
            {user.display_name.slice(0, 1)}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-800">{user.display_name}</p>
              <p className="truncate text-[11px] text-slate-400">{user.username}</p>
            </div>
          )}
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
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
    <div className="flex h-screen overflow-hidden">
      {/* 桌面侧边栏 */}
      <aside
        className={`hidden shrink-0 border-r border-slate-200/70 bg-canvas-50/80 transition-all duration-200 lg:block ${
          collapsed ? "w-[72px]" : "w-60"
        }`}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-end px-2 pt-3">
            <button
              type="button"
              onClick={() => setCollapsed((v) => !v)}
              className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
              aria-label={collapsed ? "展开侧边栏" : "收起侧边栏"}
            >
              {collapsed ? <Menu className="h-4 w-4" /> : <X className="h-4 w-4" />}
            </button>
          </div>
          {sidebar}
        </div>
      </aside>

      {/* 移动端侧边栏 */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-64 bg-canvas-50 shadow-xl">{sidebar}</div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-200/70 bg-white/80 px-4 backdrop-blur">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 lg:hidden"
            aria-label="打开菜单"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <span className="hidden text-slate-400 sm:inline">工作台</span>
            <span className="text-slate-300">/</span>
            <span className="font-medium text-slate-700">主机安全态势感知</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {mock && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700 ring-1 ring-amber-200" title="VITE_USE_MOCK 开启，数据为本地模拟">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden />
                开发模式 · 模拟数据
              </span>
            )}
            <span className="hidden text-xs text-slate-400 sm:inline">
              当前角色：
              <span className="font-medium text-slate-600">
                {user.role === "admin" ? "管理员" : user.role === "analyst" ? "分析员" : "只读用户"}
              </span>
            </span>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
