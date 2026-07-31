// 报告列表页

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { Page, ReportJob } from "@/lib/types";
import {
  EmptyState,
  Pagination,
  PageHeader,
  QueryState,
  ReportStatusBadge,
  formatTime,
} from "@/components/ui";
import { useState } from "react";

const PAGE_SIZE = 10;

export function ReportsPage() {
  const [page, setPage] = useState(1);

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["reports", page],
    queryFn: () =>
      apiGet<Page<ReportJob>>("/reports", { query: { page, page_size: PAGE_SIZE } }),
  });

  return (
    <div className="animate-fade-in">
      <PageHeader title="报告中心" description="查看安全报告的生成状态与下载" />

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
                      <th className="px-5 py-3 font-medium">发起人</th>
                      <th className="px-5 py-3 font-medium">状态</th>
                      <th className="px-5 py-3 font-medium">发起时间</th>
                      <th className="px-5 py-3 font-medium">过期时间</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {pageData.items.map((report) => (
                      <tr key={report.id} className="transition hover:bg-slate-50/60">
                        <td className="px-5 py-3">
                          <p className="font-medium text-slate-800">{report.title}</p>
                          {report.error && (
                            <p className="mt-0.5 text-xs text-rose-500">{report.error}</p>
                          )}
                        </td>
                        <td className="px-5 py-3 text-slate-600">{report.requested_by}</td>
                        <td className="px-5 py-3">
                          <ReportStatusBadge status={report.status} />
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-400">
                          {formatTime(report.requested_at)}
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-400">
                          {formatTime(report.expires_at)}
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
    </div>
  );
}
