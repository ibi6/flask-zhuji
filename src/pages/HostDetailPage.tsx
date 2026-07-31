// 主机详情页：标签页切换（概览/进程/端口/事件/基线）

import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Cpu,
  FileWarning,
  HardDrive,
  MemoryStick,
  Network,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet } from "@/lib/api";
import type { HostDetail, Severity } from "@/lib/types";
import {
  Card,
  EmptyState,
  ErrorState,
  HostStatusBadge,
  Meter,
  SeverityBadge,
  formatTime,
} from "@/components/ui";

type Tab = "overview" | "processes" | "ports" | "events" | "baseline";

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "概览" },
  { key: "processes", label: "进程" },
  { key: "ports", label: "端口" },
  { key: "events", label: "事件" },
  { key: "baseline", label: "基线" },
];

export function HostDetailPage() {
  const { hostId } = useParams<{ hostId: string }>();
  const [tab, setTab] = useState<Tab>("overview");

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["host", hostId],
    queryFn: () => apiGet<HostDetail>(`/hosts/${hostId}`),
    enabled: !!hostId,
  });

  if (isPending) {
    return (
      <div className="animate-fade-in">
        <div className="mb-4">
          <Link to="/hosts" className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700">
            <ArrowLeft className="h-3.5 w-3.5" /> 返回主机列表
          </Link>
        </div>
        <div className="space-y-3" role="status" aria-label="加载中">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="h-4 rounded bg-slate-200/70" style={{ width: `${90 - i * 8}%` }} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="animate-fade-in">
        <Link to="/hosts" className="mb-4 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700">
          <ArrowLeft className="h-3.5 w-3.5" /> 返回主机列表
        </Link>
        <ErrorState message={error.message} onRetry={() => refetch()} />
      </div>
    );
  }

  if (!data) {
    return <EmptyState title="主机不存在" description="该主机可能已被移除" />;
  }

  return (
    <div className="animate-fade-in">
      <Link to="/hosts" className="mb-4 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700">
        <ArrowLeft className="h-3.5 w-3.5" /> 返回主机列表
      </Link>

      {/* 主机头部信息 */}
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-semibold tracking-tight text-slate-900">{data.hostname}</h1>
            <HostStatusBadge status={data.status} />
          </div>
          <p className="mt-1 font-mono text-xs text-slate-400">{data.id}</p>
          <p className="mt-0.5 text-sm text-slate-500">
            {data.os === "windows" ? "Windows" : "Linux"} · {data.os_version} · {data.architecture}
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-slate-500">
          <div>
            <span className="text-slate-400">IP 地址</span>
            <p className="font-mono text-slate-700">{data.ip_addresses.join(", ")}</p>
          </div>
          <div>
            <span className="text-slate-400">Agent 版本</span>
            <p className="font-mono text-slate-700">{data.agent_version}</p>
          </div>
          <div>
            <span className="text-slate-400">纳管时间</span>
            <p className="text-slate-700">{formatTime(data.created_at)}</p>
          </div>
        </div>
      </div>

      {/* 标签页 */}
      <div className="mb-4 flex gap-1 border-b border-slate-200" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition ${
              tab === t.key
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 标签内容 */}
      {tab === "overview" && <OverviewTab host={data} />}
      {tab === "processes" && <ProcessesTab host={data} />}
      {tab === "ports" && <PortsTab host={data} />}
      {tab === "events" && <EventsTab host={data} />}
      {tab === "baseline" && <BaselineTab host={data} />}
    </div>
  );
}

function OverviewTab({ host }: { host: HostDetail }) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {host.metrics ? (
        <Card>
          <h3 className="mb-4 text-sm font-semibold text-slate-800">资源使用</h3>
          <div className="space-y-4">
            <Meter label="CPU 使用率" value={host.metrics.cpu_percent} />
            <Meter label="内存使用率" value={host.metrics.memory_percent} />
            <Meter label="磁盘使用率" value={host.metrics.disk_percent} />
          </div>
          <p className="mt-4 text-xs text-slate-400">采集时间：{formatTime(host.metrics.collected_at)}</p>
        </Card>
      ) : (
        <Card>
          <EmptyState title="暂无资源数据" description="主机离线时不会采集指标" />
        </Card>
      )}

      <Card>
        <h3 className="mb-4 text-sm font-semibold text-slate-800">基本信息</h3>
        <dl className="space-y-3 text-sm">
          <Row label="主机名" value={host.hostname} />
          <Row label="操作系统" value={`${host.os} ${host.os_version}`} />
          <Row label="架构" value={host.architecture} />
          <Row label="IP 地址" value={host.ip_addresses.join(", ")} mono />
          <Row label="Agent 版本" value={host.agent_version} mono />
          <Row label="最后心跳" value={formatTime(host.last_seen_at)} />
          {host.inventory && (
            <>
              <Row label="进程数" value={String(host.inventory.processes)} mono />
              <Row label="监听端口数" value={String(host.inventory.listening_ports)} mono />
              <Row label="启动时间" value={formatTime(host.inventory.boot_time)} />
            </>
          )}
        </dl>
      </Card>

      {host.file_changes.length > 0 && (
        <Card className="lg:col-span-2">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-800">
            <FileWarning className="h-4 w-4 text-amber-500" aria-hidden /> 文件变更
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                  <th className="py-2 pr-4 font-medium">文件路径</th>
                  <th className="py-2 pr-4 font-medium">变更类型</th>
                  <th className="py-2 pr-4 font-medium">时间</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {host.file_changes.map((fc, i) => (
                  <tr key={i}>
                    <td className="py-2 pr-4 font-mono text-xs text-slate-700">{fc.path}</td>
                    <td className="py-2 pr-4 text-slate-600">{fc.change_type}</td>
                    <td className="py-2 pr-4 text-xs text-slate-400">{formatTime(fc.occurred_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

function ProcessesTab({ host }: { host: HostDetail }) {
  if (host.process_snapshot.length === 0) {
    return <EmptyState title="暂无进程快照" description="主机离线时不会采集进程信息" />;
  }
  return (
    <Card className="p-0">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
              <th className="px-5 py-3 font-medium">PID</th>
              <th className="px-5 py-3 font-medium">进程名</th>
              <th className="px-5 py-3 font-medium">用户</th>
              <th className="px-5 py-3 font-medium">启动时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {host.process_snapshot.map((p) => (
              <tr key={p.pid} className="hover:bg-slate-50/60">
                <td className="px-5 py-2.5 font-mono text-xs text-slate-600">{p.pid}</td>
                <td className="px-5 py-2.5 font-medium text-slate-800">{p.name}</td>
                <td className="px-5 py-2.5 text-slate-600">{p.username ?? "—"}</td>
                <td className="px-5 py-2.5 text-xs text-slate-400">{formatTime(p.started_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function PortsTab({ host }: { host: HostDetail }) {
  if (host.listening_ports.length === 0) {
    return <EmptyState title="暂无监听端口" />;
  }
  return (
    <Card className="p-0">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
              <th className="px-5 py-3 font-medium">协议</th>
              <th className="px-5 py-3 font-medium">本地地址</th>
              <th className="px-5 py-3 font-medium">端口</th>
              <th className="px-5 py-3 font-medium">PID</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {host.listening_ports.map((p, i) => (
              <tr key={i} className="hover:bg-slate-50/60">
                <td className="px-5 py-2.5">
                  <span className="inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600">
                    {p.protocol.toUpperCase()}
                  </span>
                </td>
                <td className="px-5 py-2.5 font-mono text-xs text-slate-600">{p.local_address}</td>
                <td className="px-5 py-2.5 font-mono font-medium text-slate-800">{p.local_port}</td>
                <td className="px-5 py-2.5 font-mono text-xs text-slate-400">{p.pid ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function EventsTab({ host }: { host: HostDetail }) {
  if (host.security_events.length === 0) {
    return <EmptyState title="暂无安全事件" />;
  }
  return (
    <Card className="p-0">
      <div className="divide-y divide-slate-50">
        {host.security_events.map((ev, i) => (
          <div key={i} className="flex items-start gap-3 px-5 py-3">
            <SeverityBadge severity={ev.severity as Severity} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-800">{ev.summary}</p>
              <p className="mt-0.5 text-xs text-slate-400">
                {ev.event_type}
                {ev.source_ip && ` · 来源 ${ev.source_ip}`}
                {ev.username && ` · 用户 ${ev.username}`}
                {" · "}
                {formatTime(ev.occurred_at)}
              </p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function BaselineTab({ host }: { host: HostDetail }) {
  if (host.baseline_results.length === 0) {
    return <EmptyState title="暂无基线检查结果" />;
  }
  const statusLabel: Record<string, string> = { pass: "通过", fail: "失败", unavailable: "未评估" };
  const statusStyle: Record<string, string> = {
    pass: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    fail: "bg-rose-50 text-rose-700 ring-rose-200",
    unavailable: "bg-slate-100 text-slate-500 ring-slate-200",
  };
  return (
    <Card className="p-0">
      <div className="divide-y divide-slate-50">
        {host.baseline_results.map((r) => (
          <div key={r.check_id} className="flex items-center justify-between px-5 py-3">
            <div className="min-w-0">
              <p className="font-mono text-sm font-medium text-slate-800">{r.check_id}</p>
              <p className="mt-0.5 text-xs text-slate-400">{r.message}</p>
            </div>
            <span className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${statusStyle[r.status]}`}>
              {statusLabel[r.status] ?? r.status}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-slate-400">{label}</dt>
      <dd className={`text-slate-700 ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}

export { Cpu, HardDrive, MemoryStick, Network, ShieldCheck };
