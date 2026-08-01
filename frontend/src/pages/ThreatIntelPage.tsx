// 威胁情报 — IOC（IP/域名/哈希）管理与封禁

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldBan, ShieldOff } from "lucide-react";
import { useState } from "react";
import { apiGet, apiPatch } from "@/lib/api";
import type { Page, ThreatIndicator } from "@/lib/types";
import {
  EmptyState,
  Pagination,
  PageHeader,
  QueryState,
  formatTime,
} from "@/components/ui";

const PAGE_SIZE = 10;

const IOC_OPTIONS: { value: ThreatIndicator["ioc_type"] | "all"; label: string }[] = [
  { value: "all", label: "全部类型" },
  { value: "ip", label: "IP" },
  { value: "domain", label: "域名" },
  { value: "hash", label: "哈希" },
];

const IOC_LABELS: Record<ThreatIndicator["ioc_type"], string> = {
  ip: "IP",
  domain: "域名",
  hash: "哈希",
};

export function ThreatIntelPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [iocType, setIocType] = useState<ThreatIndicator["ioc_type"] | "all">("all");

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["threat-intel", page, iocType],
    queryFn: () =>
      apiGet<Page<ThreatIndicator>>("/threat-intel", {
        query: {
          page,
          page_size: PAGE_SIZE,
          ioc_type: iocType !== "all" ? iocType : undefined,
        },
      }),
  });

  const blockMutation = useMutation({
    mutationFn: ({ id, blocked }: { id: string; blocked: boolean }) =>
      apiPatch<ThreatIndicator>(`/threat-intel/${id}`, { blocked }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["threat-intel"] }),
  });

  return (
    <div className="animate-fade-in">
      <PageHeader title="威胁情报" description="恶意 IP / 域名 / 样本哈希 IOC 库，支持一键封禁" />

      <div className="mb-4">
        <select
          className="input max-w-[140px]"
          value={iocType}
          onChange={(e) => {
            setIocType(e.target.value as ThreatIndicator["ioc_type"] | "all");
            setPage(1);
          }}
          aria-label="按 IOC 类型筛选"
        >
          {IOC_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
        {(pdata) =>
          pdata.items.length === 0 ? (
            <EmptyState title="暂无威胁情报" description="当前筛选条件下没有 IOC 记录" />
          ) : (
            <>
              <div className="card overflow-x-auto p-0">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b text-xs uppercase tracking-wide" style={{ borderColor: "var(--divider)", color: "var(--text-muted)" }}>
                      <th className="px-4 py-3 font-medium">类型</th>
                      <th className="px-4 py-3 font-medium">IOC 值</th>
                      <th className="px-4 py-3 font-medium">威胁类型</th>
                      <th className="px-4 py-3 font-medium">置信度</th>
                      <th className="px-4 py-3 font-medium">来源</th>
                      <th className="px-4 py-3 font-medium">最近出现</th>
                      <th className="px-4 py-3 font-medium">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pdata.items.map((ti) => (
                    <tr key={ti.id} className="border-b last:border-0 hover:bg-black/[0.02]" style={{ borderColor: "var(--divider)" }}>
                      <td className="px-4 py-3">
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                          {IOC_LABELS[ti.ioc_type]}
                        </span>
                      </td>
                      <td className="max-w-xs truncate px-4 py-3 font-mono text-xs">{ti.value}</td>
                      <td className="px-4 py-3">{ti.threat_type}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                            <div
                              className="h-full rounded-full bg-indigo-500"
                              style={{ width: `${ti.confidence}%` }}
                            />
                          </div>
                          <span className="text-xs text-slate-500">{ti.confidence}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">{ti.source}</td>
                      <td className="px-4 py-3 text-xs text-slate-500">{formatTime(ti.last_seen)}</td>
                      <td className="px-4 py-3">
                        {ti.blocked ? (
                          <button
                            type="button"
                            className="btn-secondary !py-1 text-xs"
                            disabled={blockMutation.isPending}
                            onClick={() => blockMutation.mutate({ id: ti.id, blocked: false })}
                          >
                            <ShieldOff className="mr-1 inline h-3.5 w-3.5" aria-hidden />
                            解除封禁
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="btn-primary !py-1 text-xs"
                            disabled={blockMutation.isPending}
                            onClick={() => blockMutation.mutate({ id: ti.id, blocked: true })}
                          >
                            <ShieldBan className="mr-1 inline h-3.5 w-3.5" aria-hidden />
                            封禁
                          </button>
                        )}
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
