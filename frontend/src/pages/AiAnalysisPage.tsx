// AI 安全分析 — 攻击链、风险评分与处置建议

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Sparkles } from "lucide-react";
import { useState } from "react";
import { apiGet } from "@/lib/api";
import type { AiAnalysisReport, Page } from "@/lib/types";
import {
  EmptyState,
  Modal,
  Pagination,
  PageHeader,
  QueryState,
  formatTime,
} from "@/components/ui";

const PAGE_SIZE = 6;

const RISK_STYLES: Record<AiAnalysisReport["risk_level"], string> = {
  low: "bg-sky-50 text-sky-700 ring-sky-200",
  medium: "bg-amber-50 text-amber-700 ring-amber-200",
  high: "bg-orange-50 text-orange-700 ring-orange-200",
  critical: "bg-rose-50 text-rose-700 ring-rose-200",
};

const RISK_LABELS: Record<AiAnalysisReport["risk_level"], string> = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "严重",
};

export function AiAnalysisPage() {
  const [page, setPage] = useState(1);
  const [detail, setDetail] = useState<AiAnalysisReport | null>(null);

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["ai-analysis", page],
    queryFn: () => apiGet<Page<AiAnalysisReport>>("/ai-analysis", { query: { page, page_size: PAGE_SIZE } }),
  });

  const openDetail = async (report: AiAnalysisReport) => {
    const full = await apiGet<AiAnalysisReport>(`/ai-analysis/${report.id}`);
    setDetail(full);
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="AI 安全分析"
        description="基于告警与资产关联的智能态势解读、攻击链还原与处置建议"
        actions={
          <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 ring-1 ring-indigo-100">
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
            Mock 推理引擎
          </span>
        }
      />

      <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
        {(pdata) =>
          pdata.items.length === 0 ? (
            <EmptyState title="暂无分析报告" description="系统将在检测到关联告警后自动生成分析" />
          ) : (
            <>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {pdata.items.map((report) => (
                <button
                  key={report.id}
                  type="button"
                  className="card text-left transition hover:shadow-lg"
                  onClick={() => openDetail(report)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-slate-800">{report.title}</h3>
                      <p className="mt-1 text-xs text-slate-500">{formatTime(report.generated_at)}</p>
                    </div>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${RISK_STYLES[report.risk_level]}`}>
                      {RISK_LABELS[report.risk_level]}风险 · {report.risk_score}
                    </span>
                  </div>
                  <p className="mt-3 line-clamp-2 text-sm text-slate-600">{report.summary}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {report.attack_chain.slice(0, 3).map((step, i) => (
                      <span key={step} className="inline-flex items-center text-xs text-slate-500">
                        {i > 0 && <ChevronRight className="mx-0.5 h-3 w-3" aria-hidden />}
                        {step}
                      </span>
                    ))}
                    {report.attack_chain.length > 3 && (
                      <span className="text-xs text-slate-400">+{report.attack_chain.length - 3}</span>
                    )}
                  </div>
                  <p className="mt-2 text-xs text-indigo-600">关联告警 {report.related_alert_count} 条 · 点击查看详情</p>
                </button>
              ))}
            </div>
            <Pagination page={page} total={pdata.total} pageSize={PAGE_SIZE} onChange={setPage} />
          </>
          )
        }
      </QueryState>

      {detail && (
        <Modal onClose={() => setDetail(null)} title={detail.title}>
          <div className="space-y-4 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${RISK_STYLES[detail.risk_level]}`}>
                风险等级：{RISK_LABELS[detail.risk_level]}（{detail.risk_score} 分）
              </span>
              <span className="text-xs text-slate-500">生成于 {formatTime(detail.generated_at)}</span>
            </div>
            <p className="leading-relaxed text-slate-700">{detail.summary}</p>

            <section>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">攻击链</h4>
              <ol className="flex flex-wrap items-center gap-1">
                {detail.attack_chain.map((step, i) => (
                  <li key={step} className="inline-flex items-center">
                    {i > 0 && <ChevronRight className="mx-1 h-4 w-4 text-slate-300" aria-hidden />}
                    <span className="rounded-lg bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-100">
                      {step}
                    </span>
                  </li>
                ))}
              </ol>
            </section>

            <section>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">受影响主机</h4>
              <div className="flex flex-wrap gap-1.5">
                {detail.affected_hosts.map((h) => (
                  <span key={h} className="rounded-md bg-indigo-50 px-2 py-0.5 font-mono text-xs text-indigo-700">
                    {h}
                  </span>
                ))}
              </div>
            </section>

            <section>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">处置建议</h4>
              <ul className="list-inside list-disc space-y-1 text-slate-700">
                {detail.recommendations.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </section>
          </div>
        </Modal>
      )}
    </div>
  );
}
