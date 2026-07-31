// 主机列表页

import { useQuery } from "@tanstack/react-query";
import { Search, Server } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "@/lib/api";
import type { Host, Page } from "@/lib/types";
import {
  EmptyState,
  ErrorState,
  HostStatusBadge,
  Pagination,
  PageHeader,
  formatTime,
} from "@/components/ui";

const PAGE_SIZE = 10;

export function HostsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const query = useQuery({
    queryKey: ["hosts", page, search],
    queryFn: () =>
      apiGet<Page<Host>>("/hosts", {
        query: { page, page_size: PAGE_SIZE, q: search || undefined },
      }),
  });

  const { data, isPending, error, refetch } = query;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="主机管理"
        description="查看纳管主机的状态、系统信息与最后心跳时间"
      />

      <div className="mb-4 flex items-center gap-3">
        <div className="relative max-w-xs flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <input
            type="search"
            className="input pl-9"
            placeholder="搜索主机名或 IP…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            aria-label="搜索主机"
          />
        </div>
      </div>

      <div className="card overflow-hidden p-0">
        {isPending ? (
          <div className="space-y-3 p-5" role="status" aria-label="加载中">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="h-4 rounded bg-slate-200/70" style={{ width: `${90 - i * 8}%` }} />
            ))}
          </div>
        ) : error ? (
          <ErrorState message={error.message} onRetry={() => refetch()} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            title={search ? "未找到匹配的主机" : "暂无主机"}
            description={search ? "尝试更换关键词" : "纳管主机后将在此显示"}
            action={
              <Link to="/overview" className="btn-secondary text-xs">
                返回总览
              </Link>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                  <th className="px-5 py-3 font-medium">主机名</th>
                  <th className="px-5 py-3 font-medium">IP 地址</th>
                  <th className="px-5 py-3 font-medium">操作系统</th>
                  <th className="px-5 py-3 font-medium">状态</th>
                  <th className="px-5 py-3 font-medium">最后心跳</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {data.items.map((host) => (
                  <tr key={host.id} className="transition hover:bg-slate-50/60">
                    <td className="px-5 py-3">
                      <Link
                        to={`/hosts/${host.id}`}
                        className="flex items-center gap-2 font-medium text-slate-800 hover:text-brand-600"
                      >
                        <Server className="h-3.5 w-3.5 text-slate-400" aria-hidden />
                        {host.hostname}
                      </Link>
                      {host.source === "simulated" && (
                        <span className="ml-2 inline-flex rounded bg-violet-50 px-1.5 py-0.5 text-[10px] font-medium text-violet-600 ring-1 ring-violet-200">
                          模拟
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3 font-mono text-xs text-slate-600">
                      {host.ip_addresses.join(", ")}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      <span className="capitalize">{host.os}</span>
                      <span className="ml-1 text-xs text-slate-400">{host.os_version}</span>
                    </td>
                    <td className="px-5 py-3">
                      <HostStatusBadge status={host.status} />
                    </td>
                    <td className="px-5 py-3 text-xs text-slate-500">
                      {formatTime(host.last_seen_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {data && data.total > PAGE_SIZE && (
        <Pagination
          page={data.page}
          pageSize={data.page_size}
          total={data.total}
          onChange={setPage}
        />
      )}
    </div>
  );
}
