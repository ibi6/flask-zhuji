// 用户管理页：admin 专用

import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import { apiGet } from "@/lib/api";
import type { Page, User } from "@/lib/types";
import {
  EmptyState,
  Pagination,
  PageHeader,
  QueryState,
  RoleBadge,
  formatTime,
} from "@/components/ui";
import { useAuth } from "@/store/auth";
import { useState } from "react";

const PAGE_SIZE = 20;

export function UsersPage() {
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const canAccess = !user || user.role === "admin";

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["users", page],
    queryFn: () => apiGet<Page<User>>("/users", { query: { page, page_size: PAGE_SIZE } }),
    enabled: canAccess,
  });

  if (!canAccess) {
    return <Navigate to="/overview" replace />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader title="用户管理" description="管理平台用户与角色" />

      <div className="card overflow-hidden p-0">
        <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
          {(pageData) =>
            pageData.items.length === 0 ? (
              <EmptyState title="暂无用户" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                      <th className="px-5 py-3 font-medium">用户名</th>
                      <th className="px-5 py-3 font-medium">显示名</th>
                      <th className="px-5 py-3 font-medium">角色</th>
                      <th className="px-5 py-3 font-medium">状态</th>
                      <th className="px-5 py-3 font-medium">最后登录</th>
                      <th className="px-5 py-3 font-medium">创建时间</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {pageData.items.map((u) => (
                      <tr key={u.id} className="transition hover:bg-slate-50/60">
                        <td className="px-5 py-3 font-mono text-slate-700">{u.username}</td>
                        <td className="px-5 py-3 font-medium text-slate-800">{u.display_name}</td>
                        <td className="px-5 py-3">
                          <RoleBadge role={u.role} />
                        </td>
                        <td className="px-5 py-3">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${
                              u.is_active
                                ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                                : "bg-slate-100 text-slate-500 ring-slate-200"
                            }`}
                          >
                            {u.is_active ? "启用" : "禁用"}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-400">{formatTime(u.last_login_at)}</td>
                        <td className="px-5 py-3 text-xs text-slate-400">{formatTime(u.created_at)}</td>
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
