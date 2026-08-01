// 告警中心页：筛选、单条/批量状态流转（open→investigating→resolved/ignored）、详情与状态历史

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckSquare2, Download, Eye, History } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { apiGet, apiPost } from "@/lib/api";
import { downloadCsv } from "@/lib/exportCsv";
import type { Alert, AlertDetail, AlertStatus, Page, Severity } from "@/lib/types";
import {
  AlertStatusBadge,
  EmptyState,
  Field,
  Modal,
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

/** 各状态允许流转到的下一个状态 */
export const NEXT_STATUS: Record<AlertStatus, AlertStatus[]> = {
  open: ["investigating", "resolved", "ignored"],
  investigating: ["resolved", "ignored"],
  resolved: [],
  ignored: [],
};

const STATUS_LABELS: Record<AlertStatus, string> = {
  open: "未处理",
  investigating: "调查中",
  resolved: "已解决",
  ignored: "已忽略",
};

export function AlertsPage() {
  const queryClient = useQueryClient();
  const location = useLocation();
  const [page, setPage] = useState(1);
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [status, setStatus] = useState<AlertStatus | "all">("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [transition, setTransition] = useState<{ ids: string[]; alerts: Alert[] } | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [exporting, setExporting] = useState(false);

  const exportAlerts = async () => {
    setExporting(true);
    try {
      const result = await apiGet<Page<Alert>>("/alerts", {
        query: {
          page: 1,
          page_size: 500,
          severity: severity !== "all" ? severity : undefined,
          status: status !== "all" ? status : undefined,
        },
      });
      const headers = ["ID", "摘要", "严重级别", "状态", "主机", "规则", "首次触发", "最近更新", "处理人"];
      const rows = result.items.map((a) => [
        a.id,
        a.summary,
        a.severity,
        STATUS_LABELS[a.status],
        a.hostname,
        a.rule_name,
        a.occurred_at,
        a.updated_at,
        a.assignee ?? "",
      ]);
      const stamp = new Date().toISOString().slice(0, 10);
      downloadCsv(`hostguard-alerts-${stamp}.csv`, headers, rows);
    } finally {
      setExporting(false);
    }
  };

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

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // 从 Dashboard 跳转：打开详情或处置弹窗
  useEffect(() => {
    const state = location.state as {
      detailId?: string;
      transitionId?: string;
      toStatus?: AlertStatus;
    } | null;
    if (!state || !data?.items) return;

    if (state.detailId) {
      setDetailId(state.detailId);
    }
    if (state.transitionId) {
      const alert = data.items.find((a) => a.id === state.transitionId);
      if (alert) {
        setTransition({ ids: [alert.id], alerts: [alert] });
        setComment("");
      }
    }
    window.history.replaceState({}, document.title);
  }, [location.state, data]);

  const transitionMutation = useMutation({
    mutationFn: ({ ids, toStatus, note }: { ids: string[]; toStatus: AlertStatus; note: string }) =>
      Promise.all(ids.map((id) => apiPost<AlertDetail>(`/alerts/${id}/transitions`, { to_status: toStatus, comment: note || undefined }))),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      setSelected(new Set());
      setTransition(null);
      setComment("");
    },
  });

  const openSingle = (alert: Alert) => {
    setTransition({ ids: [alert.id], alerts: [alert] });
    setComment("");
  };

  const submitTransition = (toStatus: AlertStatus) => {
    if (!transition) return;
    transitionMutation.mutate({ ids: transition.ids, toStatus, note: comment });
  };

  const pageData = data;
  const pageIds = pageData?.items.map((a) => a.id) ?? [];
  const allChecked = pageIds.length > 0 && pageIds.every((id) => selected.has(id));

  const toggleAll = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allChecked) pageIds.forEach((id) => next.delete(id));
      else pageIds.forEach((id) => next.add(id));
      return next;
    });
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="告警中心"
        description="查看与处置安全告警，支持单条/批量状态流转"
        actions={
          <button
            type="button"
            className="btn-secondary"
            disabled={exporting}
            onClick={() => void exportAlerts()}
          >
            <Download className="h-4 w-4" aria-hidden />
            {exporting ? "导出中…" : "导出 Excel"}
          </button>
        }
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
        {selected.size > 0 && (
          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-slate-500">
              已选 <span className="font-semibold text-slate-700">{selected.size}</span> 条
            </span>
            <button
              type="button"
              className="btn-secondary !py-1.5 text-xs"
              onClick={() => {
                const list = pageData?.items.filter((a) => selected.has(a.id)) ?? [];
                setTransition({ ids: [...selected], alerts: list });
                setComment("");
              }}
            >
              <CheckSquare2 className="h-3.5 w-3.5" aria-hidden />
              批量处置
            </button>
            <button type="button" className="text-xs text-slate-400 hover:text-slate-600" onClick={() => setSelected(new Set())}>
              取消选择
            </button>
          </div>
        )}
      </div>

      <div className="card overflow-hidden p-0">
        <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
          {(pdata) =>
            pdata.items.length === 0 ? (
              <EmptyState title="暂无告警" description="当前筛选条件下没有告警记录" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                      <th className="w-10 px-4 py-3">
                        <input
                          type="checkbox"
                          aria-label="选择当前页全部告警"
                          checked={allChecked}
                          onChange={toggleAll}
                          className="h-3.5 w-3.5 accent-brand-600"
                        />
                      </th>
                      <th className="px-5 py-3 font-medium">时间</th>
                      <th className="px-5 py-3 font-medium">主机</th>
                      <th className="px-5 py-3 font-medium">级别</th>
                      <th className="px-5 py-3 font-medium">标题</th>
                      <th className="px-5 py-3 font-medium">状态</th>
                      <th className="px-5 py-3 text-right font-medium">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {pdata.items.map((alert) => {
                      const next = NEXT_STATUS[alert.status];
                      const isSelected = selected.has(alert.id);
                      return (
                        <tr key={alert.id} className={`transition hover:bg-slate-50/60 ${isSelected ? "bg-brand-50/40" : ""}`}>
                          <td className="px-4 py-3">
                            <input
                              type="checkbox"
                              aria-label={`选择告警 ${alert.summary}`}
                              checked={isSelected}
                              onChange={() => toggle(alert.id)}
                              className="h-3.5 w-3.5 accent-brand-600"
                            />
                          </td>
                          <td className="whitespace-nowrap px-5 py-3 text-xs text-slate-400">
                            {formatTime(alert.occurred_at)}
                          </td>
                          <td className="px-5 py-3">
                            <Link to={`/hosts/${alert.host_id}`} className="font-medium text-slate-700 hover:text-brand-600">
                              {alert.hostname}
                            </Link>
                          </td>
                          <td className="px-5 py-3">
                            <SeverityBadge severity={alert.severity} />
                          </td>
                          <td className="px-5 py-3">
                            <button
                              type="button"
                              onClick={() => setDetailId(alert.id)}
                              className="text-left text-slate-800 hover:text-brand-600"
                              title="查看详情"
                            >
                              <p className="font-medium">{alert.summary}</p>
                              <p className="mt-0.5 text-xs text-slate-400">规则：{alert.rule_name}</p>
                            </button>
                          </td>
                          <td className="px-5 py-3">
                            <AlertStatusBadge status={alert.status} />
                          </td>
                          <td className="px-5 py-3">
                            <div className="flex items-center justify-end gap-1">
                              {next.length > 0 && (
                                <button
                                  type="button"
                                  className="btn-secondary !px-2.5 !py-1 text-xs"
                                  onClick={() => openSingle(alert)}
                                >
                                  处置
                                </button>
                              )}
                              <button
                                type="button"
                                className="btn-secondary !px-2.5 !py-1 text-xs"
                                onClick={() => setDetailId(alert.id)}
                              >
                                <Eye className="h-3.5 w-3.5" aria-hidden />
                                详情
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
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

      {/* 单条/批量状态流转弹窗 */}
      {transition && (
        <TransitionModal
          alerts={transition.alerts}
          ids={transition.ids}
          comment={comment}
          onComment={setComment}
          isPending={transitionMutation.isPending}
          error={transitionMutation.error}
          onClose={() => setTransition(null)}
          onSubmit={submitTransition}
        />
      )}

      {/* 告警详情与状态历史 */}
      {detailId && (
        <AlertDetailModal alertId={detailId} onClose={() => setDetailId(null)} onTransition={(alert) => {
          setDetailId(null);
          openSingle(alert);
        }} />
      )}
    </div>
  );
}

function TransitionModal({
  alerts,
  ids,
  comment,
  onComment,
  isPending,
  error,
  onClose,
  onSubmit,
}: {
  alerts: Alert[];
  ids: string[];
  comment: string;
  onComment: (v: string) => void;
  isPending: boolean;
  error: Error | null;
  onClose: () => void;
  onSubmit: (toStatus: AlertStatus) => void;
}) {
  const [target, setTarget] = useState<AlertStatus>("investigating");
  const isBatch = ids.length > 1;
  // 批量时合并所有可选目标状态
  const allowed = [...new Set(alerts.flatMap((a) => NEXT_STATUS[a.status]))];

  return (
    <Modal
      title={isBatch ? `批量处置（${ids.length} 条告警）` : "处置告警"}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={isPending}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={isPending || !allowed.includes(target)}
            onClick={() => onSubmit(target)}
          >
            {isPending ? "提交中…" : "确认处置"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        {isBatch ? (
          <p className="rounded-xl bg-canvas-50 px-3 py-2 text-xs text-slate-500">
            将对选中的 <span className="font-semibold text-slate-700">{ids.length}</span> 条告警执行同一状态流转。
          </p>
        ) : (
          alerts[0] && (
            <div className="rounded-xl bg-canvas-50 px-3 py-2.5">
              <p className="text-sm font-medium text-slate-800">{alerts[0].summary}</p>
              <p className="mt-0.5 text-xs text-slate-500">
                {alerts[0].hostname} · <SeverityBadge severity={alerts[0].severity} /> · 当前 <AlertStatusBadge status={alerts[0].status} />
              </p>
            </div>
          )
        )}
        <Field label="流转到">
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="选择目标状态">
            {allowed.map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={target === s}
                onClick={() => setTarget(s)}
                className={`rounded-xl px-3 py-2 text-sm font-medium ring-1 transition ${
                  target === s
                    ? "bg-brand-600 text-white ring-brand-600"
                    : "bg-white text-slate-600 ring-slate-200 hover:bg-slate-50"
                }`}
              >
                {STATUS_LABELS[s]}
              </button>
            ))}
            {allowed.length === 0 && <p className="text-xs text-slate-400">当前状态不可流转</p>}
          </div>
        </Field>
        <Field label="处置备注" hint="选填，将记录在状态历史中">
          <textarea
            className="input min-h-[80px] resize-y"
            value={comment}
            onChange={(e) => onComment(e.target.value)}
            placeholder="例如：确认是计划内变更…"
            aria-label="处置备注"
          />
        </Field>
        {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700 ring-1 ring-rose-200" role="alert">{error.message}</p>}
      </div>
    </Modal>
  );
}

function AlertDetailModal({
  alertId,
  onClose,
  onTransition,
}: {
  alertId: string;
  onClose: () => void;
  onTransition: (alert: Alert) => void;
}) {
  const { data, isPending, error } = useQuery({
    queryKey: ["alert", "detail", alertId],
    queryFn: () => apiGet<AlertDetail>(`/alerts/${alertId}`),
    enabled: !!alertId,
  });

  return (
    <Modal
      title="告警详情"
      onClose={onClose}
      wide
      footer={
        data && NEXT_STATUS[data.status].length > 0 ? (
          <button type="button" className="btn-primary" onClick={() => onTransition(data)}>
            处置此告警
          </button>
        ) : undefined
      }
    >
      {isPending ? (
        <div className="space-y-3" role="status" aria-label="加载中">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="h-4 rounded bg-slate-200/70" style={{ width: `${90 - i * 10}%` }} />
          ))}
        </div>
      ) : error ? (
        <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700 ring-1 ring-rose-200">{error.message}</p>
      ) : data ? (
        <div className="space-y-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-semibold text-slate-900">{data.summary}</h3>
              <SeverityBadge severity={data.severity} />
              <AlertStatusBadge status={data.status} />
            </div>
            <dl className="mt-3 grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
              <InfoRow label="主机" value={data.hostname} />
              <InfoRow label="触发规则" value={data.rule_name} />
              <InfoRow label="发生时间" value={formatTime(data.occurred_at)} />
              <InfoRow label="更新时间" value={formatTime(data.updated_at)} />
              <InfoRow label="负责人" value={data.assignee ?? "未指派"} />
              <InfoRow label="告警 ID" value={data.id} mono />
            </dl>
            {data.details && (
              <p className="mt-3 rounded-xl bg-canvas-50 px-3 py-2.5 text-xs leading-relaxed text-slate-600">{data.details}</p>
            )}
          </div>

          <div className="border-t border-slate-100 pt-4">
            <h4 className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-slate-800">
              <History className="h-4 w-4 text-slate-400" aria-hidden /> 状态历史
            </h4>
            {data.transitions.length === 0 ? (
              <p className="text-xs text-slate-400">暂无流转记录（告警自创建以来状态未变化）</p>
            ) : (
              <ol className="space-y-3 border-l border-slate-200 pl-4">
                <li className="relative">
                  <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full bg-brand-500 ring-4 ring-brand-100" aria-hidden />
                  <p className="text-sm font-medium text-slate-700">告警创建</p>
                  <p className="text-xs text-slate-400">{formatTime(data.occurred_at)} · 初始状态 {STATUS_LABELS.open}</p>
                </li>
                {data.transitions.map((t) => (
                  <li key={t.id} className="relative">
                    <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full bg-slate-300 ring-4 ring-slate-100" aria-hidden />
                    <p className="text-sm text-slate-700">
                      {STATUS_LABELS[t.from_status]} <span aria-hidden>→</span> {STATUS_LABELS[t.to_status]}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-400">
                      {formatTime(t.occurred_at)} · {t.actor}
                    </p>
                    {t.comment && <p className="mt-1 text-xs text-slate-500">备注：{t.comment}</p>}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

function InfoRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="shrink-0 text-slate-400">{label}</dt>
      <dd className={`truncate text-slate-700 ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}
