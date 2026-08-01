// 安全总览页：真实 KPI（在线主机、告警分布、风险趋势）

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Server,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { apiGet } from "@/lib/api";
import type { DashboardSummary, Severity } from "@/lib/types";
import { AlertStatusBadge, Card, QueryState, SeverityBadge, formatTime } from "@/components/ui";
import { RiskTrendChart } from "@/components/charts";
import type { MultiSeriesPoint } from "@/components/charts";

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: number | string;
  sub?: string;
  icon: typeof Server;
  tone?: "default" | "danger" | "warn";
}) {
  const iconTone =
    tone === "danger"
      ? "bg-rose-50 text-rose-600"
      : tone === "warn"
        ? "bg-amber-50 text-amber-600"
        : "bg-brand-50 text-brand-600";
  return (
    <div className="card flex items-start gap-4 p-5">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${iconTone}`}>
        <Icon className="h-5 w-5" aria-hidden />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-medium text-slate-500">{label}</p>
        <p className="mt-1 font-mono text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
        {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
      </div>
    </div>
  );
}

const SEVERITY_META: { key: Severity; label: string; color: string }[] = [
  { key: "critical", label: "严重", color: "bg-rose-500" },
  { key: "high", label: "高危", color: "bg-orange-500" },
  { key: "medium", label: "中危", color: "bg-amber-400" },
  { key: "low", label: "低危", color: "bg-sky-400" },
];

export function OverviewPage() {
  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => apiGet<DashboardSummary>("/dashboard/summary"),
  });

  return (
    <div className="animate-fade-in">
      <div className="mb-5">
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">安全总览</h1>
        <p className="mt-1 text-sm text-slate-500">当前全局安全态势与关键指标</p>
      </div>

      <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
        {(summary) => {
          const distribution = summary.alert_distribution;
          const maxSeverity = Math.max(1, ...SEVERITY_META.map((s) => distribution[s.key] ?? 0));
          const trend: MultiSeriesPoint[] = summary.risk_trend.map((p) => ({
            label: p.date,
            values: { critical: p.critical, high: p.high, medium: p.medium, low: p.low },
          }));
          return (
            <div className="space-y-6">
              {/* 指标卡 */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard
                  label="主机总数"
                  value={summary.hosts_total}
                  sub={`在线 ${summary.hosts_online} · 降级 ${summary.hosts_degraded} · 离线 ${summary.hosts_offline}`}
                  icon={Server}
                />
                <StatCard
                  label="未处理告警"
                  value={summary.alerts_open}
                  sub={`严重 ${summary.alerts_critical} · 高危 ${summary.alerts_high}`}
                  icon={AlertTriangle}
                  tone={summary.alerts_critical > 0 ? "danger" : "warn"}
                />
                <StatCard label="今日新增事件" value={summary.events_today.toLocaleString()} sub="含登录、文件、端口事件" icon={Activity} />
                <StatCard label="启用规则" value={summary.rules_enabled} sub="检测规则实时生效" icon={ShieldCheck} />
              </div>

              {/* 最近告警 + 告警分布 */}
              <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
                <Card className="xl:col-span-2">
                  <div className="mb-4 flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-slate-800">最近告警</h2>
                    <Link to="/alerts" className="text-xs font-medium text-brand-600 hover:text-brand-700">
                      查看全部 →
                    </Link>
                  </div>
                  <div className="divide-y divide-slate-100">
                    {summary.recent_alerts.length === 0 && (
                      <p className="py-6 text-center text-xs text-slate-400">暂无告警</p>
                    )}
                    {summary.recent_alerts.map((alert) => (
                      <div key={alert.id} className="flex items-center gap-3 py-3">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-slate-800">{alert.summary}</p>
                          <p className="mt-0.5 text-xs text-slate-400">
                            {alert.hostname} · {alert.rule_name} · {formatTime(alert.occurred_at)}
                          </p>
                        </div>
                        <SeverityBadge severity={alert.severity} />
                        <AlertStatusBadge status={alert.status} />
                      </div>
                    ))}
                  </div>
                </Card>

                <Card>
                  <h2 className="mb-4 text-sm font-semibold text-slate-800">风险等级分布</h2>
                  <div className="space-y-4">
                    {SEVERITY_META.map((s) => {
                      const count = distribution[s.key] ?? 0;
                      const width = Math.min(100, (count / maxSeverity) * 100);
                      return (
                        <div key={s.key}>
                          <div className="mb-1 flex items-center justify-between text-xs">
                            <span className="text-slate-500">{s.label}</span>
                            <span className={`font-mono font-medium ${count > 0 ? "text-slate-700" : "text-slate-400"}`}>{count}</span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                            <div className={`h-full rounded-full ${s.color}`} style={{ width: `${width}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-400">
                    按当前全部告警的严重级别统计
                  </p>
                </Card>
              </div>

              {/* 风险趋势 */}
              <Card>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-slate-800">风险趋势（近 14 天）</h2>
                  <span className="text-xs text-slate-400">各严重级别每日新增告警量</span>
                </div>
                <RiskTrendChart points={trend} ariaLabel="近 14 天风险趋势" />
              </Card>
            </div>
          );
        }}
      </QueryState>
    </div>
  );
}

export { percentColor } from "@/components/ui";
