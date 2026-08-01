// 安全运营中心 Dashboard — 参考 EDR/SOC 风格（需求文档 §二）

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bot,
  Bug,
  Cpu,
  Eye,
  KeyRound,
  Server,
  Shield,
  ShieldCheck,
  Skull,
  Zap,
} from "lucide-react";
import { Link } from "react-router-dom";
import { apiGet } from "@/lib/api";
import type { DashboardSummary, Severity } from "@/lib/types";
import { AlertStatusBadge, Card, QueryState, SeverityBadge, formatTime } from "@/components/ui";
import {
  AttackRegionHeatmap,
  DonutChart,
  RankBarChart,
  RiskTrendChart,
  SecurityScoreGauge,
  TrendChart,
} from "@/components/charts";
import type { ChartPoint, MultiSeriesPoint } from "@/components/charts";

const ATTACK_TYPE_COLORS = ["#2563eb", "#7c3aed", "#f97316", "#ef4444", "#eab308", "#06b6d4"];

const SEVERITY_META: { key: Severity; label: string; color: string }[] = [
  { key: "critical", label: "严重", color: "bg-rose-500" },
  { key: "high", label: "高危", color: "bg-orange-500" },
  { key: "medium", label: "中危", color: "bg-amber-400" },
  { key: "low", label: "低危", color: "bg-sky-400" },
];

function SocStatCard({
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
  tone?: "default" | "danger" | "warn" | "success";
}) {
  const tones = {
    default: { bg: "var(--sidebar-active)", color: "var(--accent)" },
    danger: { bg: "rgba(248, 113, 113, 0.12)", color: "var(--danger)" },
    warn: { bg: "rgba(251, 191, 36, 0.12)", color: "var(--warning)" },
    success: { bg: "rgba(52, 211, 153, 0.12)", color: "var(--success)" },
  };
  const t = tones[tone];
  return (
    <div className="card p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: t.bg, color: t.color }}>
          <Icon className="h-5 w-5" aria-hidden />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium" style={{ color: "var(--muted)" }}>
            {label}
          </p>
          <p className="mt-0.5 font-mono text-2xl font-semibold tracking-tight">{value}</p>
          {sub && (
            <p className="mt-0.5 text-[11px]" style={{ color: "var(--muted)" }}>
              {sub}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export function OverviewPage() {
  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => apiGet<DashboardSummary>("/dashboard/summary"),
  });

  return (
    <div className="animate-fade-in">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wider" style={{ color: "var(--accent)" }}>
            Security Operations Center
          </p>
          <h1 className="text-xl font-semibold tracking-tight">安全态势总览</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            全局威胁感知 · 攻击趋势 · 资产健康 · AI 辅助分析
          </p>
        </div>
        <Link to="/alerts" className="btn-primary text-xs">
          进入告警中心
        </Link>
      </div>

      <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
        {(summary) => {
          const distribution = summary.alert_distribution;
          const maxSeverity = Math.max(1, ...SEVERITY_META.map((s) => distribution[s.key] ?? 0));
          const trend: MultiSeriesPoint[] = summary.risk_trend.map((p) => ({
            label: p.date,
            values: { critical: p.critical, high: p.high, medium: p.medium, low: p.low },
          }));
          const attack24h: ChartPoint[] = (summary.attack_trend_24h ?? []).map((p) => ({
            label: p.hour,
            value: p.count,
          }));
          const attackTypes = (summary.attack_types ?? []).map((t, i) => ({
            label: t.name,
            value: t.count,
            color: ATTACK_TYPE_COLORS[i % ATTACK_TYPE_COLORS.length]!,
          }));
          const score = summary.security_score ?? 72;
          const agentRate = summary.agent_online_rate ?? Math.round((summary.hosts_online / Math.max(1, summary.hosts_total)) * 100);

          return (
            <div className="space-y-6">
              {/* 安全评分 + 核心 KPI */}
              <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
                <Card className="flex flex-col items-center justify-center xl:col-span-2">
                  <SecurityScoreGauge score={score} />
                  <p className="mt-2 text-center text-[11px]" style={{ color: "var(--muted)" }}>
                    Agent 在线率 {agentRate}%
                  </p>
                </Card>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:col-span-10 lg:grid-cols-4">
                  <SocStatCard label="主机总数" value={summary.hosts_total} sub={`在线 ${summary.hosts_online}`} icon={Server} />
                  <SocStatCard
                    label="未处理告警"
                    value={summary.alerts_open}
                    sub={`严重 ${summary.alerts_critical}`}
                    icon={AlertTriangle}
                    tone={summary.alerts_critical > 0 ? "danger" : "warn"}
                  />
                  <SocStatCard label="攻击事件" value={summary.attack_events ?? summary.events_today} sub="近 24 小时" icon={Zap} tone="danger" />
                  <SocStatCard label="高危漏洞" value={summary.high_vulnerabilities ?? 0} sub="待修复" icon={Bug} tone="warn" />
                  <SocStatCard label="异常登录" value={summary.abnormal_logins ?? 0} icon={KeyRound} />
                  <SocStatCard label="暴力破解" value={summary.brute_force ?? 0} icon={Skull} tone="danger" />
                  <SocStatCard label="恶意进程" value={summary.malicious_processes ?? 0} icon={Cpu} tone="warn" />
                  <SocStatCard label="启用规则" value={summary.rules_enabled} sub="实时检测" icon={ShieldCheck} tone="success" />
                </div>
              </div>

              {/* 24h 攻击趋势 + 攻击类型 */}
              <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
                <Card className="xl:col-span-2">
                  <h2 className="mb-3 text-sm font-semibold">24 小时攻击趋势</h2>
                  {attack24h.length > 0 ? (
                    <TrendChart points={attack24h} color="#2563eb" formatValue={(v) => `${Math.round(v)}`} ariaLabel="24 小时攻击趋势" />
                  ) : (
                    <p className="py-8 text-center text-xs" style={{ color: "var(--muted)" }}>
                      暂无趋势数据
                    </p>
                  )}
                </Card>
                <Card>
                  <h2 className="mb-3 text-sm font-semibold">攻击类型分布</h2>
                  {attackTypes.length > 0 ? (
                    <DonutChart items={attackTypes} ariaLabel="攻击类型分布" />
                  ) : (
                    <p className="py-8 text-center text-xs" style={{ color: "var(--muted)" }}>
                      暂无数据
                    </p>
                  )}
                </Card>
              </div>

              {/* TOP 榜 + 攻击来源 + AI 分析 */}
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                <Card>
                  <h2 className="mb-3 text-sm font-semibold">TOP 攻击 IP</h2>
                  <RankBarChart items={summary.top_attack_ips ?? []} ariaLabel="TOP 攻击 IP" />
                </Card>
                <Card>
                  <h2 className="mb-3 text-sm font-semibold">TOP 受攻击主机</h2>
                  <RankBarChart items={summary.top_attacked_hosts ?? []} ariaLabel="TOP 受攻击主机" />
                </Card>
                <Card>
                  <h2 className="mb-3 text-sm font-semibold">攻击来源区域</h2>
                  <AttackRegionHeatmap regions={summary.attack_regions ?? []} />
                </Card>
              </div>

              {summary.ai_insight && (
                <Card className="border-l-4" style={{ borderLeftColor: "var(--accent)" }}>
                  <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: "var(--sidebar-active)" }}>
                      <Bot className="h-5 w-5" style={{ color: "var(--accent)" }} aria-hidden />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <h2 className="text-sm font-semibold">AI 态势分析</h2>
                        <span
                          className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                          style={{
                            background:
                              summary.ai_insight.risk_level === "high"
                                ? "rgba(248,113,113,0.12)"
                                : "rgba(251,191,36,0.12)",
                            color: summary.ai_insight.risk_level === "high" ? "var(--danger)" : "var(--warning)",
                          }}
                        >
                          {summary.ai_insight.risk_level === "high" ? "高风险" : "中风险"}
                        </span>
                      </div>
                      <p className="text-sm leading-relaxed" style={{ color: "var(--ink-soft)" }}>
                        {summary.ai_insight.summary}
                      </p>
                      <ul className="mt-3 space-y-1.5">
                        {summary.ai_insight.recommendations.map((rec) => (
                          <li key={rec} className="flex gap-2 text-xs" style={{ color: "var(--muted)" }}>
                            <Shield className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "var(--accent)" }} aria-hidden />
                            {rec}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </Card>
              )}

              {/* 最近告警 + 风险分布 */}
              <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
                <Card className="xl:col-span-2">
                  <div className="mb-4 flex items-center justify-between">
                    <h2 className="text-sm font-semibold">最近告警</h2>
                    <Link to="/alerts" className="text-xs font-medium" style={{ color: "var(--accent)" }}>
                      查看全部 →
                    </Link>
                  </div>
                  <div className="divide-y" style={{ borderColor: "var(--divider)" }}>
                    {summary.recent_alerts.length === 0 && (
                      <p className="py-6 text-center text-xs" style={{ color: "var(--muted)" }}>
                        暂无告警
                      </p>
                    )}
                    {summary.recent_alerts.map((alert) => (
                      <div key={alert.id} className="flex flex-wrap items-center gap-3 py-3">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{alert.summary}</p>
                          <p className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
                            {alert.hostname} · {alert.rule_name} · {formatTime(alert.occurred_at)}
                          </p>
                        </div>
                        <SeverityBadge severity={alert.severity} />
                        <AlertStatusBadge status={alert.status} />
                        <div className="flex shrink-0 gap-1">
                          <Link
                            to="/alerts"
                            state={{ detailId: alert.id }}
                            className="btn-secondary !px-2 !py-1 text-[11px]"
                          >
                            <Eye className="h-3 w-3" aria-hidden />
                            详情
                          </Link>
                          {alert.status === "open" && (
                            <>
                              <Link
                                to="/alerts"
                                state={{ transitionId: alert.id, toStatus: "investigating" }}
                                className="btn-primary !px-2 !py-1 text-[11px]"
                              >
                                处理
                              </Link>
                              <Link
                                to="/alerts"
                                state={{ transitionId: alert.id, toStatus: "ignored" }}
                                className="btn-secondary !px-2 !py-1 text-[11px]"
                              >
                                忽略
                              </Link>
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>

                <Card>
                  <h2 className="mb-4 text-sm font-semibold">风险等级分布</h2>
                  <div className="space-y-4">
                    {SEVERITY_META.map((s) => {
                      const count = distribution[s.key] ?? 0;
                      const width = Math.min(100, (count / maxSeverity) * 100);
                      return (
                        <div key={s.key}>
                          <div className="mb-1 flex items-center justify-between text-xs">
                            <span style={{ color: "var(--muted)" }}>{s.label}</span>
                            <span className="font-mono font-medium">{count}</span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full" style={{ background: "var(--divider)" }}>
                            <div className={`h-full rounded-full ${s.color}`} style={{ width: `${width}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Card>
              </div>

              <Card>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-semibold">风险趋势（近 14 天）</h2>
                  <span className="text-xs" style={{ color: "var(--muted)" }}>
                    各严重级别每日新增
                  </span>
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
