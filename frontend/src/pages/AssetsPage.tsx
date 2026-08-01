// 资产中心 — 主机资产、标签、部门、在线状态

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "@/lib/api";
import type { AssetRecord, HostStatus, Page } from "@/lib/types";
import {
  EmptyState,
  HostStatusBadge,
  Pagination,
  PageHeader,
  QueryState,
  formatTime,
} from "@/components/ui";

const PAGE_SIZE = 12;

const STATUS_OPTIONS: { value: HostStatus | "all"; label: string }[] = [
  { value: "all", label: "全部状态" },
  { value: "online", label: "在线" },
  { value: "degraded", label: "降级" },
  { value: "offline", label: "离线" },
];

export function AssetsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<HostStatus | "all">("all");

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["assets", page, search, status],
    queryFn: () =>
      apiGet<Page<AssetRecord>>("/assets", {
        query: {
          page,
          page_size: PAGE_SIZE,
          search: search || undefined,
          status: status !== "all" ? status : undefined,
        },
      }),
  });

  return (
    <div className="animate-fade-in">
      <PageHeader title="资产中心" description="统一资产视图：系统版本、业务标签、部门归属与 Agent 状态" />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative max-w-xs flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: "var(--input-icon)" }} aria-hidden />
          <input
            type="search"
            className="input pl-9"
            placeholder="搜索主机、系统、部门、标签…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            aria-label="搜索资产"
          />
        </div>
        <select
          className="input max-w-[140px]"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as HostStatus | "all");
            setPage(1);
          }}
          aria-label="按在线状态筛选"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
        {(pdata) =>
          pdata.items.length === 0 ? (
            <EmptyState title="暂无资产" description="调整筛选条件或等待 Agent 上报" />
          ) : (
            <>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {pdata.items.map((asset) => (
                <Link
                  key={asset.id}
                  to={`/hosts/${asset.id}`}
                  className="card group block transition hover:shadow-lg"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-semibold text-slate-800 group-hover:text-indigo-600">{asset.hostname}</h3>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {asset.os} {asset.os_version}
                      </p>
                    </div>
                    <HostStatusBadge status={asset.status} />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {asset.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700 ring-1 ring-indigo-100"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                  <dl className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500">
                    <div>
                      <dt className="text-[10px] uppercase tracking-wide">部门</dt>
                      <dd className="font-medium text-slate-700">{asset.department}</dd>
                    </div>
                    <div>
                      <dt className="text-[10px] uppercase tracking-wide">Agent</dt>
                      <dd className="font-mono text-slate-700">{asset.agent_version ?? "—"}</dd>
                    </div>
                    <div className="col-span-2">
                      <dt className="text-[10px] uppercase tracking-wide">IP</dt>
                      <dd className="font-mono text-slate-700">{asset.ip_addresses.join(", ") || "—"}</dd>
                    </div>
                    <div className="col-span-2">
                      <dt className="text-[10px] uppercase tracking-wide">最后心跳</dt>
                      <dd>{asset.last_seen_at ? formatTime(asset.last_seen_at) : "从未上报"}</dd>
                    </div>
                  </dl>
                </Link>
              ))}
            </div>
            <Pagination page={page} total={pdata.total} pageSize={PAGE_SIZE} onChange={setPage} />
          </>
          )
        }
      </QueryState>
    </div>
  );
}
