// 报告中心页：创建报告（范围/类型/格式）、状态列表、completed 可下载

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";
import { apiGet, apiGetBlob, apiPost } from "@/lib/api";
import type { Page, ReportJob } from "@/lib/types";
import {
  EmptyState,
  Field,
  Modal,
  Pagination,
  PageHeader,
  QueryState,
  ReportStatusBadge,
  formatTime,
} from "@/components/ui";

const PAGE_SIZE = 10;

const SCOPE_OPTIONS = [
  { value: "all_hosts", label: "全部主机" },
  { value: "alerts", label: "告警数据" },
  { value: "hosts", label: "主机资产" },
  { value: "baseline", label: "基线检查" },
];

const TYPE_OPTIONS = [
  { value: "summary", label: "安全态势总览" },
  { value: "alert_analysis", label: "告警分析" },
  { value: "baseline_compliance", label: "基线合规" },
];

const FORMAT_OPTIONS = [
  { value: "pdf", label: "PDF" },
  { value: "csv", label: "CSV" },
  { value: "html", label: "HTML" },
];

const SCOPE_LABELS: Record<string, string> = Object.fromEntries(SCOPE_OPTIONS.map((o) => [o.value, o.label]));
const TYPE_LABELS: Record<string, string> = Object.fromEntries(TYPE_OPTIONS.map((o) => [o.value, o.label]));

export function ReportsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["reports", page],
    queryFn: () =>
      apiGet<Page<ReportJob>>("/reports", { query: { page, page_size: PAGE_SIZE } }),
  });

  const createMutation = useMutation({
    mutationFn: (payload: { title: string; scope: string; report_type: string; format: string }) =>
      apiPost<ReportJob>("/reports", payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports"] });
      setCreating(false);
    },
  });

  const download = async (report: ReportJob) => {
    if (report.status !== "completed" || downloadingId) return;
    setDownloadingId(report.id);
    try {
      const blob = await apiGetBlob(`/reports/${report.id}/download`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${report.title}.${report.format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // 下载失败由按钮状态回退即可
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="报告中心"
        description="创建安全报告，查看生成状态并下载已完成报告"
        actions={
          <button type="button" className="btn-primary" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            新建报告
          </button>
        }
      />

      <div className="card overflow-hidden p-0">
        <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
          {(pageData) =>
            pageData.items.length === 0 ? (
              <EmptyState title="暂无报告" description="生成的安全报告将在此显示" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                      <th className="px-5 py-3 font-medium">报告名称</th>
                      <th className="px-5 py-3 font-medium">范围</th>
                      <th className="px-5 py-3 font-medium">类型</th>
                      <th className="px-5 py-3 font-medium">格式</th>
                      <th className="px-5 py-3 font-medium">发起人</th>
                      <th className="px-5 py-3 font-medium">状态</th>
                      <th className="px-5 py-3 font-medium">发起时间</th>
                      <th className="px-5 py-3 font-medium">过期时间</th>
                      <th className="px-5 py-3 text-right font-medium">下载</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {pageData.items.map((report) => (
                      <tr key={report.id} className="transition hover:bg-slate-50/60">
                        <td className="px-5 py-3">
                          <p className="font-medium text-slate-800">{report.title}</p>
                          {report.error && <p className="mt-0.5 text-xs text-rose-500">{report.error}</p>}
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-600">{SCOPE_LABELS[report.scope] ?? report.scope}</td>
                        <td className="px-5 py-3 text-xs text-slate-600">{TYPE_LABELS[report.report_type] ?? report.report_type}</td>
                        <td className="px-5 py-3">
                          <span className="inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium uppercase text-slate-600">
                            {report.format}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-slate-600">{report.requested_by}</td>
                        <td className="px-5 py-3">
                          <ReportStatusBadge status={report.status} />
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-400">{formatTime(report.requested_at)}</td>
                        <td className="px-5 py-3 text-xs text-slate-400">{formatTime(report.expires_at)}</td>
                        <td className="px-5 py-3">
                          <div className="flex justify-end">
                            {report.status === "completed" ? (
                              <button
                                type="button"
                                className="btn-secondary !px-2.5 !py-1 text-xs"
                                onClick={() => download(report)}
                                disabled={downloadingId === report.id}
                              >
                                <Download className="h-3.5 w-3.5" aria-hidden />
                                {downloadingId === report.id ? "下载中…" : "下载"}
                              </button>
                            ) : (
                              <span className="text-xs text-slate-300">—</span>
                            )}
                          </div>
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

      {data && data.total > PAGE_SIZE && (
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />
      )}

      {creating && (
        <ReportCreateModal
          isPending={createMutation.isPending}
          error={createMutation.error}
          onClose={() => setCreating(false)}
          onSubmit={(payload) => createMutation.mutate(payload)}
        />
      )}
    </div>
  );
}

function ReportCreateModal({
  isPending,
  error,
  onClose,
  onSubmit,
}: {
  isPending: boolean;
  error: Error | null;
  onClose: () => void;
  onSubmit: (payload: { title: string; scope: string; report_type: string; format: string }) => void;
}) {
  const [title, setTitle] = useState("");
  const [scope, setScope] = useState("all_hosts");
  const [reportType, setReportType] = useState("summary");
  const [format, setFormat] = useState("pdf");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    onSubmit({ title: title.trim(), scope, report_type: reportType, format });
  };

  return (
    <Modal
      title="新建报告"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={isPending}>
            取消
          </button>
          <button type="submit" form="report-create-form" className="btn-primary" disabled={isPending || !title.trim()}>
            {isPending ? "提交中…" : "生成报告"}
          </button>
        </>
      }
    >
      <form id="report-create-form" className="space-y-4" onSubmit={submit} noValidate>
        <Field label="报告名称">
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：8 月安全态势周报" aria-label="报告名称" />
        </Field>
        <Field label="数据范围">
          <select className="input" value={scope} onChange={(e) => setScope(e.target.value)} aria-label="数据范围">
            {SCOPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="报告类型">
          <select className="input" value={reportType} onChange={(e) => setReportType(e.target.value)} aria-label="报告类型">
            {TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="导出格式">
          <select className="input" value={format} onChange={(e) => setFormat(e.target.value)} aria-label="导出格式">
            {FORMAT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>
        <p className="text-xs text-slate-400">提交后将异步生成，生成完成后可在列表下载。</p>
        {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700 ring-1 ring-rose-200" role="alert">{error.message}</p>}
      </form>
    </Modal>
  );
}
