// 轻量自绘 SVG 图表组件 —— 不引第三方图表库
// 设计语言：冷色画布 + 紫/靛点缀 + 语义色

import { useId } from "react";

export interface ChartPoint {
  label: string;
  value: number;
}

export interface MultiSeriesPoint {
  label: string;
  values: Record<string, number>;
}

const VIEW_W = 560;
const PAD = { top: 16, right: 10, bottom: 22, left: 38 };

function niceBounds(min: number, max: number): [number, number] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 100];
  if (max - min < 1e-9) {
    const m = Math.max(Math.abs(max) * 0.1, 1);
    return [Math.max(0, min - m), max + m];
  }
  const span = max - min;
  return [min - span * 0.08, max + span * 0.08];
}

function buildScale(values: number[]) {
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const [lo, hi] = niceBounds(rawMin, rawMax);
  const innerW = VIEW_W - PAD.left - PAD.right;
  const x = (i: number, n: number) => PAD.left + (n <= 1 ? 0 : (i / (n - 1)) * innerW);
  const y = (v: number, h: number) => PAD.top + (1 - (v - lo) / (hi - lo)) * (h - PAD.top - PAD.bottom);
  return { lo, hi, x, y };
}

function buildLinePath(xs: number[], ys: number[]): string {
  return xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${ys[i]?.toFixed(1) ?? 0}`).join(" ");
}

/** 单条趋势面积图（CPU/内存等百分比型） */
export function TrendChart({
  points,
  color = "#6a4cc8",
  formatValue = (v) => `${v.toFixed(0)}%`,
  height = 168,
  ariaLabel = "趋势图",
}: {
  points: ChartPoint[];
  color?: string;
  formatValue?: (v: number) => string;
  height?: number;
  ariaLabel?: string;
}) {
  const gradId = useId().replace(/:/g, "");
  if (points.length === 0) return null;
  const values = points.map((p) => p.value);
  const { lo, hi, x, y } = buildScale(values);
  const xs = points.map((_, i) => x(i, points.length));
  const ys = values.map((v) => y(v, height));
  const line = buildLinePath(xs, ys);
  const area = `${line} L${xs[xs.length - 1]?.toFixed(1) ?? PAD.left},${height - PAD.bottom} L${PAD.left},${height - PAD.bottom} Z`;
  const last = points[points.length - 1];
  const gridVals = [hi, (hi + lo) / 2, lo];

  return (
    <div>
      <svg viewBox={`0 0 ${VIEW_W} ${height}`} className="w-full" role="img" aria-label={ariaLabel}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.22" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {gridVals.map((gv) => (
          <g key={gv.toFixed(1)}>
            <line x1={PAD.left} x2={VIEW_W - PAD.right} y1={y(gv, height)} y2={y(gv, height)} stroke="#e2e8f0" strokeDasharray="3 4" />
            <text x={PAD.left - 6} y={y(gv, height) + 3} textAnchor="end" fontSize="10" fill="#94a3b8">
              {formatValue(gv)}
            </text>
          </g>
        ))}
        <path d={area} fill={`url(#${gradId})`} />
        <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        {last && (
          <circle cx={xs[xs.length - 1]} cy={ys[ys.length - 1]} r="3" fill={color} />
        )}
        {/* x 轴标签 */}
        {[0, Math.floor((points.length - 1) / 2), points.length - 1].map((idx) => {
          const p = points[idx];
          if (!p) return null;
          const anchor = idx === 0 ? "start" : idx === points.length - 1 ? "end" : "middle";
          return (
            <text key={idx} x={xs[idx]} y={height - 6} textAnchor={anchor} fontSize="10" fill="#94a3b8">
              {p.label}
            </text>
          );
        })}
      </svg>
      {last && (
        <p className="mt-1 text-xs text-slate-500">
          当前 <span className="font-mono font-semibold" style={{ color }}>{formatValue(last.value)}</span>
          <span className="ml-2 text-slate-400">最低 {formatValue(lo)} · 最高 {formatValue(hi)}</span>
        </p>
      )}
    </div>
  );
}

/** 双序列趋势图（网络收发等） */
export function DualTrendChart({
  series,
  formatValue = (v) => `${v.toFixed(0)}`,
  height = 168,
  ariaLabel = "双序列趋势图",
}: {
  series: { name: string; color: string; points: ChartPoint[] }[];
  formatValue?: (v: number) => string;
  height?: number;
  ariaLabel?: string;
}) {
  const gradBase = useId().replace(/:/g, "");
  if (series.length === 0 || series[0]?.points.length === 0) return null;
  const gradIds = series.map((_, i) => `${gradBase}-${i}`);
  const n = series[0]?.points.length ?? 0;
  const allValues = series.flatMap((s) => s.points.map((p) => p.value));
  const { lo, hi, x, y } = buildScale(allValues);
  const labels = series[0]?.points.map((p) => p.label) ?? [];

  return (
    <div>
      <svg viewBox={`0 0 ${VIEW_W} ${height}`} className="w-full" role="img" aria-label={ariaLabel}>
        <defs>
          {series.map((_, i) => (
            <linearGradient key={i} id={gradIds[i]!} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={series[i]!.color} stopOpacity="0.18" />
              <stop offset="100%" stopColor={series[i]!.color} stopOpacity="0.02" />
            </linearGradient>
          ))}
        </defs>
        {[hi, (hi + lo) / 2, lo].map((gv) => (
          <g key={gv.toFixed(1)}>
            <line x1={PAD.left} x2={VIEW_W - PAD.right} y1={y(gv, height)} y2={y(gv, height)} stroke="#e2e8f0" strokeDasharray="3 4" />
            <text x={PAD.left - 6} y={y(gv, height) + 3} textAnchor="end" fontSize="10" fill="#94a3b8">
              {formatValue(gv)}
            </text>
          </g>
        ))}
        {series.map((s, si) => {
          const xs = s.points.map((_, i) => x(i, n));
          const ys = s.points.map((p) => y(p.value, height));
          const line = buildLinePath(xs, ys);
          const area = `${line} L${xs[xs.length - 1]?.toFixed(1) ?? PAD.left},${height - PAD.bottom} L${PAD.left},${height - PAD.bottom} Z`;
          const last = s.points[s.points.length - 1];
          return (
            <g key={s.name}>
              <path d={area} fill={`url(#${gradIds[si]})`} />
              <path d={line} fill="none" stroke={s.color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              {last && <circle cx={xs[xs.length - 1]} cy={ys[ys.length - 1]} r="3" fill={s.color} />}
            </g>
          );
        })}
        {[0, Math.floor((n - 1) / 2), n - 1].map((idx) => {
          const label = labels[idx];
          if (!label) return null;
          const anchor = idx === 0 ? "start" : idx === n - 1 ? "end" : "middle";
          return (
            <text key={idx} x={x(idx, n)} y={height - 6} textAnchor={anchor} fontSize="10" fill="#94a3b8">
              {label}
            </text>
          );
        })}
      </svg>
      <div className="mt-1 flex flex-wrap items-center gap-3">
        {series.map((s) => {
          const last = s.points[s.points.length - 1];
          return (
            <span key={s.name} className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: s.color }} aria-hidden />
              {s.name}
              {last && <span className="font-mono font-semibold text-slate-700">{formatValue(last.value)}</span>}
            </span>
          );
        })}
      </div>
    </div>
  );
}

/** 风险趋势堆叠面积图（近 N 天各严重级别告警量） */
export function RiskTrendChart({
  points,
  height = 168,
  ariaLabel = "风险趋势图",
}: {
  points: MultiSeriesPoint[];
  height?: number;
  ariaLabel?: string;
}) {
  const colors = { critical: "#f43f5e", high: "#fb923c", medium: "#fbbf24", low: "#38bdf8" };
  if (points.length === 0) return null;
  const keys = Object.keys(colors) as (keyof typeof colors)[];
  const allMax = Math.max(...points.map((p) => keys.reduce((sum, k) => sum + (p.values[k] ?? 0), 0)));
  const { x, y } = buildScale([0, Math.max(allMax, 1)]);
  const n = points.length;
  const xs = points.map((_, i) => x(i, n));

  // 计算各层顶部累计值并生成堆叠路径（bottomTop：该层下方所有层的累计，即该层的底部）
  const bottomTops = keys.map((_, ki) => {
    const acc: number[] = [];
    let sum = 0;
    for (const p of points) {
      sum += p.values[keys[ki]!] ?? 0;
      acc.push(sum);
    }
    return acc;
  });
  // layers 反转后逐层填充（底层在下，顶层在上）
  const areas = keys.map((key, ki) => {
    const tops = bottomTops[ki]!;
    const ys = tops.map((v) => y(v, height));
    const bottom = ki === 0 ? null : bottomTops[ki - 1]!;
    let d = xs.map((xVal, i) => `${i === 0 ? "M" : "L"}${xVal.toFixed(1)},${ys[i]?.toFixed(1) ?? 0}`).join(" ");
    for (let i = n - 1; i >= 0; i -= 1) {
      const by = bottom ? y(bottom[i]!, height) : height - PAD.bottom;
      d += ` L${xs[i]?.toFixed(1)},${by.toFixed(1)}`;
    }
    d += " Z";
    return { key, d };
  });

  const last = points[points.length - 1];

  return (
    <div>
      <svg viewBox={`0 0 ${VIEW_W} ${height}`} className="w-full" role="img" aria-label={ariaLabel}>
        {[0.5, 1].map((f) => (
          <g key={f}>
            <line x1={PAD.left} x2={VIEW_W - PAD.right} y1={y(allMax * f, height)} y2={y(allMax * f, height)} stroke="#e2e8f0" strokeDasharray="3 4" />
            <text x={PAD.left - 6} y={y(allMax * f, height) + 3} textAnchor="end" fontSize="10" fill="#94a3b8">
              {Math.round(allMax * f)}
            </text>
          </g>
        ))}
        {areas.map((a) => (
          <path key={a.key} d={a.d} fill={colors[a.key]} opacity={0.55} />
        ))}
        {[0, Math.floor((n - 1) / 2), n - 1].map((idx) => {
          const p = points[idx];
          if (!p) return null;
          const anchor = idx === 0 ? "start" : idx === n - 1 ? "end" : "middle";
          return (
            <text key={idx} x={xs[idx]} y={height - 6} textAnchor={anchor} fontSize="10" fill="#94a3b8">
              {p.label}
            </text>
          );
        })}
      </svg>
      <div className="mt-1 flex flex-wrap items-center gap-3">
        {keys.map((key) => {
          const label = { critical: "严重", high: "高危", medium: "中危", low: "低危" }[key];
          const value = last?.values[key] ?? 0;
          return (
            <span key={key} className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: colors[key] }} aria-hidden />
              {label}
              <span className="font-mono font-semibold text-slate-700">{value}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

/** 环形图（攻击类型分布） */
export function DonutChart({
  items,
  ariaLabel = "分布图",
}: {
  items: { label: string; value: number; color: string }[];
  ariaLabel?: string;
}) {
  const total = Math.max(1, items.reduce((s, i) => s + i.value, 0));
  let offset = 0;
  const r = 52;
  const c = 2 * Math.PI * r;
  const segments = items.map((item) => {
    const frac = item.value / total;
    const dash = frac * c;
    const seg = { ...item, dash, gap: c - dash, offset };
    offset += dash;
    return seg;
  });

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
      <svg viewBox="0 0 140 140" className="h-36 w-36 shrink-0" role="img" aria-label={ariaLabel}>
        <circle cx="70" cy="70" r={r} fill="none" stroke="var(--divider, #e2e8f0)" strokeWidth="14" />
        <g transform="rotate(-90 70 70)">
          {segments.map((s) => (
            <circle
              key={s.label}
              cx="70"
              cy="70"
              r={r}
              fill="none"
              stroke={s.color}
              strokeWidth="14"
              strokeDasharray={`${s.dash} ${s.gap}`}
              strokeDashoffset={-s.offset}
            />
          ))}
        </g>
        <text x="70" y="66" textAnchor="middle" fontSize="22" fontWeight="600" fill="var(--ink, #0f172a)">
          {total}
        </text>
        <text x="70" y="82" textAnchor="middle" fontSize="10" fill="var(--muted, #64748b)">
          事件
        </text>
      </svg>
      <ul className="flex-1 space-y-2">
        {items.map((item) => (
          <li key={item.label} className="flex items-center justify-between gap-2 text-xs">
            <span className="flex items-center gap-2" style={{ color: "var(--ink-soft)" }}>
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} aria-hidden />
              {item.label}
            </span>
            <span className="font-mono font-semibold" style={{ color: "var(--ink)" }}>
              {item.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RankBarChart({
  items,
  maxItems = 5,
  ariaLabel = "排行榜",
}: {
  items: { label: string; value: number; meta?: string }[];
  maxItems?: number;
  ariaLabel?: string;
}) {
  const rows = items.slice(0, maxItems);
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="space-y-3" role="list" aria-label={ariaLabel}>
      {rows.map((row, i) => (
        <li key={row.label}>
          <div className="mb-1 flex items-center justify-between gap-2 text-xs">
            <span className="flex min-w-0 items-center gap-2 truncate" style={{ color: "var(--ink-soft)" }}>
              <span
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[10px] font-bold"
                style={{ background: "var(--sidebar-active)", color: "var(--accent)" }}
              >
                {i + 1}
              </span>
              <span className="truncate font-mono">{row.label}</span>
              {row.meta && <span className="text-[10px]" style={{ color: "var(--muted)" }}>{row.meta}</span>}
            </span>
            <span className="font-mono font-semibold" style={{ color: "var(--ink)" }}>
              {row.value}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full" style={{ background: "var(--divider)" }}>
            <div
              className="h-full rounded-full"
              style={{ width: `${(row.value / max) * 100}%`, background: "linear-gradient(90deg, var(--accent), var(--cyan))" }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function SecurityScoreGauge({ score, ariaLabel = "安全评分" }: { score: number; ariaLabel?: string }) {
  const clamped = Math.min(100, Math.max(0, score));
  const color = clamped >= 80 ? "#34d399" : clamped >= 60 ? "#fbbf24" : "#f87171";
  const dash = (clamped / 100) * 251;

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 120 72" className="h-24 w-40" role="img" aria-label={ariaLabel}>
        <path d="M 12 60 A 48 48 0 0 1 108 60" fill="none" stroke="var(--divider, #e2e8f0)" strokeWidth="10" strokeLinecap="round" />
        <path
          d="M 12 60 A 48 48 0 0 1 108 60"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${dash} 251`}
        />
        <text x="60" y="52" textAnchor="middle" fontSize="26" fontWeight="700" fill="var(--ink, #0f172a)">
          {clamped}
        </text>
        <text x="60" y="68" textAnchor="middle" fontSize="10" fill="var(--muted, #64748b)">
          安全评分
        </text>
      </svg>
      <p className="text-center text-xs" style={{ color: "var(--muted)" }}>
        {clamped >= 80 ? "整体态势良好" : clamped >= 60 ? "存在需关注风险" : "建议立即处置"}
      </p>
    </div>
  );
}

export function AttackRegionHeatmap({
  regions,
  ariaLabel = "攻击来源分布",
}: {
  regions: { region: string; count: number }[];
  ariaLabel?: string;
}) {
  const max = Math.max(1, ...regions.map((r) => r.count));
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="img" aria-label={ariaLabel}>
      {regions.map((r) => {
        const intensity = 0.25 + (r.count / max) * 0.75;
        return (
          <div
            key={r.region}
            className="rounded-xl border p-3 text-center"
            style={{ borderColor: "var(--glass-border)", background: `rgba(77, 141, 255, ${intensity * 0.15})` }}
          >
            <p className="text-xs font-medium" style={{ color: "var(--ink-soft)" }}>
              {r.region}
            </p>
            <p className="mt-1 font-mono text-lg font-semibold" style={{ color: "var(--accent)" }}>
              {r.count}
            </p>
          </div>
        );
      })}
    </div>
  );
}
