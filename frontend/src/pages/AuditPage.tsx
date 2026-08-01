// 审计日志页：viewer 及以上可读（与 contracts 一致）

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { apiGet } from "@/lib/api";
import type { AuditEvent, Page } from "@/lib/types";
import {
  EmptyState,
  Pagination,
  PageHeader,
  QueryState,
  formatTime,
} from "@/components/ui";

const PAGE_SIZE = 20;

export function AuditPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["audit", page, search],
    queryFn: () =>
      apiGet<Page<AuditEvent>>("/audit", {
        query: { page, page_size: PAGE_SIZE, q: search || undefined },
      }),
  });

  const outcomeStyle: Record<string, string> = {
    success: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    failure: "bg-rose-50 text-rose-700 ring-rose-200",
  };

  return (
    <div className="animate-fade-in">
      <PageHeader title="审计日志" description="平台所有用户操作与安全事件的审计记录" />

      <div className="mb-4 flex items-center gap-3">
        <div className="relative max-w-xs flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: "var(--input-icon)" }} aria-hidden />
          <input
            type="search"
            className="input pl-9"
            placeholder="搜索操作人、动作…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            aria-label="搜索审计日志"
          />
        </div>
      </div>

      <div className="card overflow-hidden p-0">
        <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
          {(pageData) =>
            pageData.items.length === 0 ? (
              <EmptyState title="暂无审计日志" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                      <th className="px-5 py-3 font-medium">时间</th>
                      <th className="px-5 py-3 font-medium">操作人</th>
                      <th className="px-5 py-3 font-medium">操作</th>
                      <th className="px-5 py-3 font-medium">资源</th>
                      <th className="px-5 py-3 font-medium">结果</th>
                      <th className="px-5 py-3 font-medium">详情</th>
                      <th className="px-5 py-3 font-medium">IP</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {pageData.items.map((ev) => (
                      <tr key={ev.id} className="transition hover:bg-slate-50/60">
                        <td className="whitespace-nowrap px-5 py-3 text-xs text-slate-400">
                          {formatTime(ev.occurred_at)}
                        </td>
                        <td className="px-5 py-3 font-medium text-slate-700">{ev.actor}</td>
                        <td className="px-5 py-3 font-mono text-xs text-slate-600">{ev.action}</td>
                        <td className="px-5 py-3 text-slate-600">
                          {ev.resource_type}
                          {ev.resource_id && (
                            <span className="ml-1 font-mono text-xs text-slate-400">
                              {ev.resource_id.slice(0, 8)}
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-3">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${
                              outcomeStyle[ev.outcome] ?? "bg-slate-100 text-slate-500 ring-slate-200"
                            }`}
                          >
                            {ev.outcome === "success" ? "成功" : "失败"}
                          </span>
                        </td>
                        <td className="max-w-xs truncate px-5 py-3 text-xs text-slate-500" title={ev.detail ?? ""}>
                          {ev.detail ?? "—"}
                        </td>
                        <td className="px-5 py-3 font-mono text-xs text-slate-400">{ev.ip ?? "—"}</td>
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
