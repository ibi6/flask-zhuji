// 漏洞管理 — CVE 列表、等级筛选、修复状态更新

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPatch } from "@/lib/api";
import type { Page, Severity, Vulnerability, VulnFixStatus } from "@/lib/types";
import {
  EmptyState,
  Pagination,
  PageHeader,
  QueryState,
  SeverityBadge,
  formatTime,
} from "@/components/ui";

const PAGE_SIZE = 10;

const SEVERITY_OPTIONS: { value: Severity | "all"; label: string }[] = [
  { value: "all", label: "全部级别" },
  { value: "critical", label: "严重" },
  { value: "high", label: "高危" },
  { value: "medium", label: "中危" },
  { value: "low", label: "低危" },
];

const FIX_OPTIONS: { value: VulnFixStatus | "all"; label: string }[] = [
  { value: "all", label: "全部状态" },
  { value: "open", label: "未修复" },
  { value: "in_progress", label: "修复中" },
  { value: "fixed", label: "已修复" },
  { value: "accepted", label: "已接受" },
];

const FIX_LABELS: Record<VulnFixStatus, string> = {
  open: "未修复",
  in_progress: "修复中",
  fixed: "已修复",
  accepted: "已接受",
};

export function VulnerabilitiesPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [fixStatus, setFixStatus] = useState<VulnFixStatus | "all">("all");

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["vulnerabilities", page, severity, fixStatus],
    queryFn: () =>
      apiGet<Page<Vulnerability>>("/vulnerabilities", {
        query: {
          page,
          page_size: PAGE_SIZE,
          severity: severity !== "all" ? severity : undefined,
          fix_status: fixStatus !== "all" ? fixStatus : undefined,
        },
      }),
  });

  const patchMutation = useMutation({
    mutationFn: ({ id, fix_status }: { id: string; fix_status: VulnFixStatus }) =>
      apiPatch<Vulnerability>(`/vulnerabilities/${id}`, { fix_status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["vulnerabilities"] }),
  });

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="漏洞管理"
        description="CVE 漏洞台账、CVSS 评分与修复进度跟踪"
      />

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
          value={fixStatus}
          onChange={(e) => {
            setFixStatus(e.target.value as VulnFixStatus | "all");
            setPage(1);
          }}
          aria-label="按修复状态筛选"
        >
          {FIX_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
        {(pdata) =>
          pdata.items.length === 0 ? (
            <EmptyState title="暂无漏洞记录" description="当前筛选条件下没有匹配的 CVE" />
          ) : (
            <>
              <div className="card overflow-x-auto p-0">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b text-xs uppercase tracking-wide" style={{ borderColor: "var(--divider)", color: "var(--text-muted)" }}>
                      <th className="px-4 py-3 font-medium">CVE / 标题</th>
                      <th className="px-4 py-3 font-medium">主机</th>
                      <th className="px-4 py-3 font-medium">级别</th>
                      <th className="px-4 py-3 font-medium">CVSS</th>
                      <th className="px-4 py-3 font-medium">发现时间</th>
                      <th className="px-4 py-3 font-medium">修复状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pdata.items.map((v) => (
                      <tr key={v.id} className="border-b last:border-0 hover:bg-black/[0.02]" style={{ borderColor: "var(--divider)" }}>
                        <td className="px-4 py-3">
                          <div className="font-mono text-xs font-semibold text-indigo-600">{v.cve_id}</div>
                          <div className="mt-0.5 max-w-md truncate text-slate-700">{v.title}</div>
                        </td>
                        <td className="px-4 py-3">
                          <Link to={`/hosts/${v.host_id}`} className="text-indigo-600 hover:underline">
                            {v.hostname}
                          </Link>
                        </td>
                        <td className="px-4 py-3">
                          <SeverityBadge severity={v.severity} />
                        </td>
                        <td className="px-4 py-3 font-mono text-sm">{v.cvss_score.toFixed(1)}</td>
                        <td className="px-4 py-3 text-xs text-slate-500">{formatTime(v.discovered_at)}</td>
                        <td className="px-4 py-3">
                          <select
                            className="input !py-1 text-xs"
                            value={v.fix_status}
                            disabled={patchMutation.isPending}
                            onChange={(e) =>
                              patchMutation.mutate({ id: v.id, fix_status: e.target.value as VulnFixStatus })
                            }
                            aria-label={`更新 ${v.cve_id} 修复状态`}
                          >
                            {(Object.keys(FIX_LABELS) as VulnFixStatus[]).map((s) => (
                              <option key={s} value={s}>
                                {FIX_LABELS[s]}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} total={pdata.total} pageSize={PAGE_SIZE} onChange={setPage} />
            </>
          )
        }
      </QueryState>
    </div>
  );
}
