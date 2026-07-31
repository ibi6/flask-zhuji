// 告警列表页

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "@/lib/api";
import type { Alert, AlertStatus, Page, Severity } from "@/lib/types";
import {
  AlertStatusBadge,
  EmptyState,
  Pagination,
  PageHeader,
  QueryState,
  SeverityBadge,
  formatTime,
} from "@/components/ui";

const PAGE_SIZE = 15;

const SEVERITY_OPTIONS: { value: Severity | "all"; label: string }[] = [
  { value: "all", label: "全部级别" },
  { value: "critical", label: "严重" },
  { value: "high", label: "高危" },
  { value: "medium", label: "中危" },
  { value: "low", label: "低危" },
];

const STATUS_OPTIONS: { value: AlertStatus | "all"; label: string }[] = [
  { value: "all", label: "全部状态" },
  { value: "open", label: "未处理" },
  { value: "investigating", label: "调查中" },
  { value: "resolved", label: "已解决" },
  { value: "ignored", label: "已忽略" },
];

export function AlertsPage() {
  const [page, setPage] = useState(1);
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [status, setStatus] = useState<AlertStatus | "all">("all");

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["alerts", page, severity, status],
    queryFn: () =>
      apiGet<Page<Alert>>("/alerts", {
        query: {
          page,
          page_size: PAGE_SIZE,
          severity: severity !== "all" ? severity : undefined,
          status: status !== "all" ? status : undefined,
        },
      }),
  });

  return (
    <div className="animate-fade-in">
      <PageHeader title="告警中心" description="查看与处理安全告警，按严重级别和状态筛选" />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select
          className="input max-w-[140px]"
          value={severity}
          onChange={(e) => {
            setSeverity(e.target.value as Severity | "all");
            setPage(1);
          }}
          aria-label="按严重级别筛选"
        >
          {SEVERITY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          className="input max-w-[140px]"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as AlertStatus | "all");
            setPage(1);
          }}
          aria-label="按状态筛选"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className="card overflow-hidden p-0">
        <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
          {(pageData) =>
            pageData.items.length === 0 ? (
              <EmptyState title="暂无告警" description="当前筛选条件下没有告警记录" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                      <th className="px-5 py-3 font-medium">时间</th>
                      <th className="px-5 py-3 font-medium">主机</th>
                      <th className="px-5 py-3 font-medium">级别</th>
                      <th className="px-5 py-3 font-medium">标题</th>
                      <th className="px-5 py-3 font-medium">状态</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {pageData.items.map((alert) => (
                      <tr key={alert.id} className="transition hover:bg-slate-50/60">
                        <td className="whitespace-nowrap px-5 py-3 text-xs text-slate-400">
                          {formatTime(alert.occurred_at)}
                        </td>
                        <td className="px-5 py-3">
                          <Link
                            to={`/hosts/${alert.host_id}`}
                            className="font-medium text-slate-700 hover:text-brand-600"
                          >
                            {alert.hostname}
                          </Link>
                        </td>
                        <td className="px-5 py-3">
                          <SeverityBadge severity={alert.severity} />
                        </td>
                        <td className="px-5 py-3">
                          <p className="text-slate-800">{alert.summary}</p>
                          <p className="mt-0.5 text-xs text-slate-400">规则：{alert.rule_name}</p>
                        </td>
                        <td className="px-5 py-3">
                          <AlertStatusBadge status={alert.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </QueryState>
      </div>

      {data && data.total > PAGE_SIZE && (
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />
      )}
    </div>
  );
}
