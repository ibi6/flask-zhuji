// 共享 UI 组件：状态徽标、卡片、空态/错误态/加载态、分页等

import { AlertTriangle, Inbox, RefreshCw, X } from "lucide-react";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import type { AlertStatus, DeliveryStatus, HostStatus, ReportStatus, Role, Severity } from "../lib/types";

// ---- 语义状态徽标 ----

const severityStyles: Record<Severity, string> = {
  critical: "bg-rose-50 text-rose-700 ring-rose-200",
  high: "bg-orange-50 text-orange-700 ring-orange-200",
  medium: "bg-amber-50 text-amber-700 ring-amber-200",
  low: "bg-sky-50 text-sky-700 ring-sky-200",
};

const severityLabels: Record<Severity, string> = {
  critical: "严重",
  high: "高危",
  medium: "中危",
  low: "低危",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${severityStyles[severity]}`}
    >
      {severityLabels[severity]}
    </span>
  );
}

const statusStyles: Record<HostStatus, string> = {
  online: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  degraded: "bg-amber-50 text-amber-700 ring-amber-200",
  offline: "bg-slate-100 text-slate-500 ring-slate-200",
};

const statusLabels: Record<HostStatus, string> = {
  online: "在线",
  degraded: "降级",
  offline: "离线",
};

export function HostStatusBadge({ status }: { status: HostStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${statusStyles[status]}`}
    >
      <span className="relative flex h-1.5 w-1.5">
        {status === "online" && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
        )}
        <span
          className={`relative inline-flex h-1.5 w-1.5 rounded-full ${
            status === "online" ? "bg-emerald-500" : status === "degraded" ? "bg-amber-500" : "bg-slate-400"
          }`}
        />
      </span>
      {statusLabels[status]}
    </span>
  );
}

const alertStatusStyles: Record<AlertStatus, string> = {
  open: "bg-rose-50 text-rose-700 ring-rose-200",
  investigating: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  resolved: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  ignored: "bg-slate-100 text-slate-500 ring-slate-200",
};

const alertStatusLabels: Record<AlertStatus, string> = {
  open: "未处理",
  investigating: "调查中",
  resolved: "已解决",
  ignored: "已忽略",
};

export function AlertStatusBadge({ status }: { status: AlertStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${alertStatusStyles[status]}`}
    >
      {alertStatusLabels[status]}
    </span>
  );
}

const reportStatusStyles: Record<ReportStatus, string> = {
  pending: "bg-slate-100 text-slate-600 ring-slate-200",
  running: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  completed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  failed: "bg-rose-50 text-rose-700 ring-rose-200",
  expired: "bg-amber-50 text-amber-700 ring-amber-200",
};

const reportStatusLabels: Record<ReportStatus, string> = {
  pending: "排队中",
  running: "生成中",
  completed: "已完成",
  failed: "失败",
  expired: "已过期",
};

export function ReportStatusBadge({ status }: { status: ReportStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${reportStatusStyles[status]}`}
    >
      {reportStatusLabels[status]}
    </span>
  );
}

const roleStyles: Record<Role, string> = {
  admin: "bg-violet-50 text-violet-700 ring-violet-200",
  analyst: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  viewer: "bg-slate-100 text-slate-600 ring-slate-200",
};

const roleLabels: Record<Role, string> = {
  admin: "管理员",
  analyst: "分析员",
  viewer: "只读用户",
};

export function RoleBadge({ role }: { role: Role }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${roleStyles[role]}`}
    >
      {roleLabels[role]}
    </span>
  );
}

// ---- 页面骨架 ----

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card p-5 ${className}`}>{children}</div>;
}

// ---- 状态组件 ----

export function SkeletonRow({ rows = 6 }: { rows?: number }) {
  return (
    <div className="animate-pulse space-y-3" role="status" aria-label="加载中">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-4 rounded bg-slate-200/70" style={{ width: `${100 - (i % 4) * 12}%` }} />
      ))}
    </div>
  );
}

export function EmptyState({ title = "暂无数据", description, action }: { title?: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
      <Inbox className="h-8 w-8 text-slate-300" aria-hidden />
      <p className="text-sm font-medium text-slate-600">{title}</p>
      {description && <p className="max-w-sm text-xs text-slate-400">{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <AlertTriangle className="h-8 w-8 text-rose-400" aria-hidden />
      <p className="text-sm font-medium text-slate-700">加载失败</p>
      <p className="max-w-md text-xs text-slate-400">{message}</p>
      {onRetry && (
        <button type="button" className="btn-secondary" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          重试
        </button>
      )}
    </div>
  );
}

export function QueryState<T>({
  data,
  isPending,
  error,
  onRetry,
  children,
}: {
  data: T | undefined;
  isPending: boolean;
  error: Error | null;
  onRetry?: () => void;
  children: (data: T) => ReactNode;
}) {
  if (isPending) return <SkeletonRow rows={4} />;
  if (error) return <ErrorState message={error.message} onRetry={onRetry} />;
  if (data === undefined) return <EmptyState />;
  return <>{children(data)}</>;
}

// ---- 分页 ----

export function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;
  const pages = Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
    const start = Math.max(1, Math.min(page - 3, totalPages - 6));
    return start + i;
  });
  return (
    <nav className="mt-4 flex items-center justify-between" aria-label="分页">
      <p className="text-xs text-slate-500">
        共 <span className="font-medium text-slate-700">{total}</span> 条，第 {page}/{totalPages} 页
      </p>
      <div className="flex items-center gap-1">
        <button
          type="button"
          className="btn-secondary !px-2.5 !py-1 text-xs"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          上一页
        </button>
        {pages.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onChange(p)}
            aria-current={p === page ? "page" : undefined}
            className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
              p === page ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {p}
          </button>
        ))}
        <button
          type="button"
          className="btn-secondary !px-2.5 !py-1 text-xs"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
        >
          下一页
        </button>
      </div>
    </nav>
  );
}

// ---- 表单辅助与弹窗 ----

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-slate-700">{label}</label>
      {children}
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 items-center rounded-full transition ${checked ? "bg-brand-600" : "bg-slate-300"} ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
      role="switch"
      aria-checked={checked}
      aria-label={label}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition ${checked ? "translate-x-4" : "translate-x-0.5"}`}
      />
    </button>
  );
}

export function Modal({
  title,
  onClose,
  children,
  footer,
  wide,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    panelRef.current?.focus();
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-slate-900/40" onClick={onClose} />
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`relative w-full overflow-hidden rounded-t-2xl bg-white shadow-pop outline-none sm:rounded-2xl ${wide ? "sm:max-w-2xl" : "sm:max-w-md"}`}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            aria-label="关闭"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

const deliveryStatusStyles: Record<DeliveryStatus, string> = {
  pending: "bg-slate-100 text-slate-600 ring-slate-200",
  retrying: "bg-amber-50 text-amber-700 ring-amber-200",
  sent: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  failed: "bg-rose-50 text-rose-700 ring-rose-200",
};

const deliveryStatusLabels: Record<DeliveryStatus, string> = {
  pending: "待发送",
  retrying: "重试中",
  sent: "已送达",
  failed: "失败",
};

export function DeliveryStatusBadge({ status }: { status: DeliveryStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${deliveryStatusStyles[status]}`}
    >
      {deliveryStatusLabels[status] ?? status}
    </span>
  );
}

// ---- 格式化工具 ----

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = "B";
  for (const u of units) {
    if (value < 1024) break;
    value /= 1024;
    unit = u;
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${unit}`;
}

export function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const now = Date.now();
  const diffMin = Math.round((now - d.getTime()) / 60_000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `${diffH} 小时前`;
  const diffD = Math.round(diffH / 24);
  if (diffD < 7) return `${diffD} 天前`;
  return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function percentColor(value: number): string {
  if (value >= 90) return "text-rose-600";
  if (value >= 75) return "text-amber-600";
  return "text-emerald-600";
}

export function meterColor(value: number): string {
  if (value >= 90) return "bg-rose-500";
  if (value >= 75) return "bg-amber-500";
  return "bg-brand-500";
}

export function Meter({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-slate-500">{label}</span>
        <span className={`font-mono font-medium ${percentColor(value)}`}>{value.toFixed(1)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className={`h-full rounded-full ${meterColor(value)}`} style={{ width: `${Math.min(100, value)}%` }} />
      </div>
    </div>
  );
}
