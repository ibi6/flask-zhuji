// 主机列表页 — 卡片 + 列表双视图（需求文档 §四）

import { useQuery } from "@tanstack/react-query";
import { LayoutGrid, List, Search, Server } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiGet } from "@/lib/api";
import type { Host, Page } from "@/lib/types";
import {
  EmptyState,
  ErrorState,
  HostStatusBadge,
  Meter,
  Pagination,
  PageHeader,
  formatTime,
} from "@/components/ui";

const PAGE_SIZE = 10;

type ViewMode = "list" | "card";

export function HostsPage() {
  const [searchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState(searchParams.get("q") ?? "");
  const [view, setView] = useState<ViewMode>("card");

  useEffect(() => {
    const q = searchParams.get("q");
    if (q) setSearch(q);
  }, [searchParams]);

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
        description="资产卡片与列表双模式，查看纳管主机状态与 Agent 心跳"
        actions={
          <div className="flex rounded-xl border p-0.5" style={{ borderColor: "var(--divider)" }}>
            <button
              type="button"
              onClick={() => setView("card")}
              className={`flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium transition ${view === "card" ? "btn-primary !py-1.5" : ""}`}
              aria-pressed={view === "card"}
            >
              <LayoutGrid className="h-3.5 w-3.5" aria-hidden />
              卡片
            </button>
            <button
              type="button"
              onClick={() => setView("list")}
              className={`flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium transition ${view === "list" ? "btn-primary !py-1.5" : ""}`}
              aria-pressed={view === "list"}
            >
              <List className="h-3.5 w-3.5" aria-hidden />
              列表
            </button>
          </div>
        }
      />

      <div className="mb-4 flex items-center gap-3">
        <div className="relative max-w-xs flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: "var(--input-icon)" }} aria-hidden />
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

      {isPending ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3" role="status" aria-label="加载中">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="card h-36 animate-pulse" />
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
      ) : view === "card" ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.items.map((host) => (
            <Link key={host.id} to={`/hosts/${host.id}`} className="card block p-5 transition hover:shadow-md">
              <div className="mb-3 flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" style={{ background: "var(--sidebar-active)" }}>
                    <Server className="h-4 w-4" style={{ color: "var(--accent)" }} aria-hidden />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{host.hostname}</p>
                    <p className="truncate font-mono text-[11px]" style={{ color: "var(--muted)" }}>
                      {host.ip_addresses[0]}
                    </p>
                  </div>
                </div>
                <HostStatusBadge status={host.status} />
              </div>
              <p className="mb-3 text-xs capitalize" style={{ color: "var(--muted)" }}>
                {host.os} · {host.os_version}
              </p>
              {host.metrics && (
                <div className="space-y-2">
                  <Meter value={host.metrics.cpu_percent} label="CPU" />
                  <Meter value={host.metrics.memory_percent} label="内存" />
                </div>
              )}
              <p className="mt-3 text-[11px]" style={{ color: "var(--muted)" }}>
                Agent {host.agent_version ?? "—"} · 心跳 {formatTime(host.last_seen_at)}
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs" style={{ borderColor: "var(--divider)", color: "var(--muted)" }}>
                  <th className="px-5 py-3 font-medium">主机名</th>
                  <th className="px-5 py-3 font-medium">IP 地址</th>
                  <th className="px-5 py-3 font-medium">操作系统</th>
                  <th className="px-5 py-3 font-medium">状态</th>
                  <th className="px-5 py-3 font-medium">最后心跳</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--divider)" }}>
                {data.items.map((host) => (
                  <tr key={host.id} className="transition hover:bg-[var(--table-hover)]">
                    <td className="px-5 py-3">
                      <Link to={`/hosts/${host.id}`} className="flex items-center gap-2 font-medium hover:opacity-80">
                        <Server className="h-3.5 w-3.5" style={{ color: "var(--muted)" }} aria-hidden />
                        {host.hostname}
                      </Link>
                    </td>
                    <td className="px-5 py-3 font-mono text-xs">{host.ip_addresses.join(", ")}</td>
                    <td className="px-5 py-3 text-xs capitalize">
                      {host.os} <span style={{ color: "var(--muted)" }}>{host.os_version}</span>
                    </td>
                    <td className="px-5 py-3">
                      <HostStatusBadge status={host.status} />
                    </td>
                    <td className="px-5 py-3 text-xs" style={{ color: "var(--muted)" }}>
                      {formatTime(host.last_seen_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data && data.total > PAGE_SIZE && (
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />
      )}
    </div>
  );
}
