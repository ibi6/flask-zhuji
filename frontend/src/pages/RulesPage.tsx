// 检测规则列表页：admin 可启用/禁用，其他人只读

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { apiGet, apiPatch } from "@/lib/api";
import type { DetectionRule } from "@/lib/types";
import {
  EmptyState,
  PageHeader,
  QueryState,
  SeverityBadge,
  formatTime,
} from "@/components/ui";
import { useAuth } from "@/store/auth";

export function RulesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const queryClient = useQueryClient();

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["rules"],
    queryFn: () => apiGet<DetectionRule[]>("/rules"),
  });

  const toggleMutation = useMutation({
    mutationFn: (rule: DetectionRule) =>
      apiPatch<DetectionRule>(`/rules/${rule.id}`, { enabled: !rule.enabled }),
    onSuccess: (updated) => {
      queryClient.setQueryData<DetectionRule[]>(["rules"], (old) =>
        old ? old.map((r) => (r.id === updated.id ? updated : r)) : old,
      );
    },
  });

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="检测规则"
        description={isAdmin ? "管理检测规则的启用状态" : "查看检测规则（只读）"}
      />

      <div className="card overflow-hidden p-0">
        <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
          {(rules) =>
            rules.length === 0 ? (
              <EmptyState title="暂无检测规则" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                      <th className="px-5 py-3 font-medium">规则名称</th>
                      <th className="px-5 py-3 font-medium">级别</th>
                      <th className="px-5 py-3 font-medium">类型</th>
                      <th className="px-5 py-3 font-medium">阈值</th>
                      <th className="px-5 py-3 font-medium">更新时间</th>
                      <th className="px-5 py-3 font-medium">状态</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {rules.map((rule) => (
                      <tr key={rule.id} className="transition hover:bg-slate-50/60">
                        <td className="px-5 py-3">
                          <p className="font-medium text-slate-800">{rule.name}</p>
                          <p className="mt-0.5 text-xs text-slate-400">{rule.description}</p>
                        </td>
                        <td className="px-5 py-3">
                          <SeverityBadge severity={rule.severity} />
                        </td>
                        <td className="px-5 py-3">
                          <span className="inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600">
                            {rule.kind}
                          </span>
                        </td>
                        <td className="px-5 py-3 font-mono text-xs text-slate-500">
                          {rule.threshold} / {Math.round(rule.window_seconds / 60)}min
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-400">
                          {formatTime(rule.updated_at)}
                        </td>
                        <td className="px-5 py-3">
                          {isAdmin ? (
                            <button
                              type="button"
                              disabled={toggleMutation.isPending}
                              onClick={() => toggleMutation.mutate(rule)}
                              className={`relative inline-flex h-5 w-9 items-center rounded-full transition ${
                                rule.enabled ? "bg-brand-600" : "bg-slate-300"
                              } ${toggleMutation.isPending ? "opacity-50" : ""}`}
                              role="switch"
                              aria-checked={rule.enabled}
                              aria-label={rule.enabled ? "禁用规则" : "启用规则"}
                            >
                              <span
                                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition ${
                                  rule.enabled ? "translate-x-4" : "translate-x-0.5"
                                }`}
                              />
                            </button>
                          ) : (
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${
                                rule.enabled
                                  ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                                  : "bg-slate-100 text-slate-500 ring-slate-200"
                              }`}
                            >
                              {rule.enabled ? (
                                <>
                                  <ShieldCheck className="h-3 w-3" /> 已启用
                                </>
                              ) : (
                                "已禁用"
                              )}
                            </span>
                          )}
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

      {!isAdmin && data && data.length > 0 && (
        <p className="mt-4 text-center text-xs text-slate-400">
          当前角色无修改权限，如需调整规则请联系管理员
        </p>
      )}
    </div>
  );
}
