// 通知配置页：admin 专用

import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import { apiGet } from "@/lib/api";
import type { NotificationChannel } from "@/lib/types";
import {
  EmptyState,
  PageHeader,
  QueryState,
  formatTime,
} from "@/components/ui";
import { useAuth } from "@/store/auth";

export function NotificationsPage() {
  const { user } = useAuth();
  if (user && user.role !== "admin") {
    return <Navigate to="/overview" replace />;
  }

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["notifications", "channels"],
    queryFn: () => apiGet<NotificationChannel[]>("/notifications/channels"),
  });

  const typeLabel: Record<string, string> = {
    email: "邮件",
    webhook: "Webhook",
    wecom: "企业微信",
  };

  return (
    <div className="animate-fade-in">
      <PageHeader title="通知配置" description="管理告警通知渠道与投递记录" />

      <div className="card overflow-hidden p-0">
        <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
          {(channels) =>
            channels.length === 0 ? (
              <EmptyState title="暂无通知渠道" description="配置后将通过渠道推送告警" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                      <th className="px-5 py-3 font-medium">名称</th>
                      <th className="px-5 py-3 font-medium">类型</th>
                      <th className="px-5 py-3 font-medium">目标</th>
                      <th className="px-5 py-3 font-medium">状态</th>
                      <th className="px-5 py-3 font-medium">创建时间</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {channels.map((ch) => (
                      <tr key={ch.id} className="transition hover:bg-slate-50/60">
                        <td className="px-5 py-3 font-medium text-slate-800">{ch.name}</td>
                        <td className="px-5 py-3">
                          <span className="inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600">
                            {typeLabel[ch.type] ?? ch.type}
                          </span>
                        </td>
                        <td className="max-w-xs truncate px-5 py-3 font-mono text-xs text-slate-500" title={ch.target}>
                          {ch.target}
                        </td>
                        <td className="px-5 py-3">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${
                              ch.enabled
                                ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                                : "bg-slate-100 text-slate-500 ring-slate-200"
                            }`}
                          >
                            {ch.enabled ? "启用" : "禁用"}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-400">{formatTime(ch.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </QueryState>
      </div>
    </div>
  );
}
