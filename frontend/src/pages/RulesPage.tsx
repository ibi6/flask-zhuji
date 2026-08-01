// 检测规则页：admin 可创建/编辑/启停规则，analyst/viewer 只读
// 规则编辑器：名称/严重级别/条件字段/阈值/启用

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, ShieldCheck } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import type { DetectionRule, Severity } from "@/lib/types";
import {
  EmptyState,
  Field,
  Modal,
  PageHeader,
  QueryState,
  SeverityBadge,
  Toggle,
  formatTime,
} from "@/components/ui";
import { useAuth } from "@/store/auth";

const KIND_FIELDS: Record<string, string[]> = {
  metric: ["cpu_percent", "memory_percent", "disk_percent", "network_bytes_recv"],
  event: ["login_failures", "process_kill", "privilege_escalation"],
  fim: ["file_changes"],
  port: ["high_risk_port"],
  baseline: ["baseline_fails"],
};

const FIELD_LABELS: Record<string, string> = {
  cpu_percent: "CPU 使用率 (%)",
  memory_percent: "内存使用率 (%)",
  disk_percent: "磁盘使用率 (%)",
  network_bytes_recv: "网络下行速率 (B/s)",
  login_failures: "登录失败次数",
  process_kill: "进程终止事件数",
  privilege_escalation: "提权事件数",
  file_changes: "敏感文件变更数",
  high_risk_port: "高危端口数",
  baseline_fails: "基线失败项数",
};

const KIND_LABELS: Record<string, string> = {
  metric: "指标",
  event: "事件",
  fim: "文件完整性",
  port: "端口",
  baseline: "基线",
};

/** 规则分类（需求文档 §五） */
const RULE_CATEGORIES: Record<string, string> = {
  metric: "系统安全",
  event: "账号安全",
  fim: "文件监控",
  port: "网络监控",
  baseline: "系统安全",
};

const SEVERITIES: Severity[] = ["low", "medium", "high", "critical"];
const OPS = [">=", ">", "<", "==", "!="];

interface RuleForm {
  name: string;
  description: string;
  severity: Severity;
  kind: string;
  condition_field: string;
  condition_op: string;
  threshold: number;
  window_seconds: number;
  enabled: boolean;
}

const EMPTY_FORM: RuleForm = {
  name: "",
  description: "",
  severity: "medium",
  kind: "metric",
  condition_field: "cpu_percent",
  condition_op: ">=",
  threshold: 80,
  window_seconds: 300,
  enabled: true,
};

function toForm(rule: DetectionRule): RuleForm {
  return {
    name: rule.name,
    description: rule.description,
    severity: rule.severity,
    kind: rule.kind,
    condition_field: rule.condition_field,
    condition_op: rule.condition_op,
    threshold: rule.threshold,
    window_seconds: rule.window_seconds,
    enabled: rule.enabled,
  };
}

export function RulesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const queryClient = useQueryClient();

  const [editor, setEditor] = useState<{ mode: "create" } | { mode: "edit"; rule: DetectionRule } | null>(null);

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["rules"],
    queryFn: () => apiGet<DetectionRule[]>("/rules"),
  });

  const saveMutation = useMutation({
    mutationFn: ({ form, ruleId }: { form: RuleForm; ruleId?: string }) => {
      const payload = {
        name: form.name,
        description: form.description,
        severity: form.severity,
        kind: form.kind,
        condition_field: form.condition_field,
        condition_op: form.condition_op,
        threshold: Number(form.threshold),
        window_seconds: Number(form.window_seconds),
        enabled: form.enabled,
      };
      return ruleId
        ? apiPatch<DetectionRule>(`/rules/${ruleId}`, payload)
        : apiPost<DetectionRule>("/rules", payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
      setEditor(null);
    },
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
        description={isAdmin ? "创建、编辑并启停检测规则" : "查看检测规则（只读）"}
        actions={
          isAdmin ? (
            <button type="button" className="btn-primary" onClick={() => setEditor({ mode: "create" })}>
              <Plus className="h-4 w-4" aria-hidden />
              新建规则
            </button>
          ) : undefined
        }
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
                      <th className="px-5 py-3 font-medium">分类</th>
                      <th className="px-5 py-3 font-medium">级别</th>
                      <th className="px-5 py-3 font-medium">类型</th>
                      <th className="px-5 py-3 font-medium">条件</th>
                      <th className="px-5 py-3 font-medium">更新时间</th>
                      <th className="px-5 py-3 font-medium">状态</th>
                      {isAdmin && <th className="px-5 py-3 text-right font-medium">操作</th>}
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
                          <span className="inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1" style={{ background: "var(--sidebar-active)", color: "var(--accent)", borderColor: "var(--glass-border)" }}>
                            {RULE_CATEGORIES[rule.kind] ?? "其他"}
                          </span>
                        </td>
                        <td className="px-5 py-3">
                          <SeverityBadge severity={rule.severity} />
                        </td>
                        <td className="px-5 py-3">
                          <span className="inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600">
                            {KIND_LABELS[rule.kind] ?? rule.kind}
                          </span>
                        </td>
                        <td className="px-5 py-3 font-mono text-xs text-slate-500">
                          {FIELD_LABELS[rule.condition_field] ?? rule.condition_field} {rule.condition_op} {rule.threshold}
                          <span className="text-slate-400"> / {Math.round(rule.window_seconds / 60)}min</span>
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-400">
                          {formatTime(rule.updated_at)}
                        </td>
                        <td className="px-5 py-3">
                          {isAdmin ? (
                            <Toggle
                              checked={rule.enabled}
                              onChange={() => toggleMutation.mutate(rule)}
                              disabled={toggleMutation.isPending}
                              label={rule.enabled ? "禁用规则" : "启用规则"}
                            />
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
                                  <ShieldCheck className="h-3 w-3" aria-hidden /> 已启用
                                </>
                              ) : (
                                "已禁用"
                              )}
                            </span>
                          )}
                        </td>
                        {isAdmin && (
                          <td className="px-5 py-3">
                            <div className="flex justify-end">
                              <button
                                type="button"
                                className="btn-secondary !px-2.5 !py-1 text-xs"
                                onClick={() => setEditor({ mode: "edit", rule })}
                              >
                                编辑
                              </button>
                            </div>
                          </td>
                        )}
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

      {editor && (
        <RuleEditorModal
          initial={editor.mode === "edit" ? toForm(editor.rule) : EMPTY_FORM}
          isEdit={editor.mode === "edit"}
          isPending={saveMutation.isPending}
          error={saveMutation.error}
          onClose={() => setEditor(null)}
          onSave={(form) => saveMutation.mutate({ form, ruleId: editor.mode === "edit" ? editor.rule.id : undefined })}
        />
      )}
    </div>
  );
}

function RuleEditorModal({
  initial,
  isEdit,
  isPending,
  error,
  onClose,
  onSave,
}: {
  initial: RuleForm;
  isEdit: boolean;
  isPending: boolean;
  error: Error | null;
  onClose: () => void;
  onSave: (form: RuleForm) => void;
}) {
  const [form, setForm] = useState<RuleForm>(initial);
  const set = <K extends keyof RuleForm>(key: K, value: RuleForm[K]) => setForm((f) => ({ ...f, [key]: value }));
  const fields = KIND_FIELDS[form.kind] ?? KIND_FIELDS.metric!;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    onSave({ ...form, name: form.name.trim() });
  };

  return (
    <Modal
      title={isEdit ? "编辑规则" : "新建规则"}
      onClose={onClose}
      wide
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={isPending}>
            取消
          </button>
          <button type="submit" form="rule-editor-form" className="btn-primary" disabled={isPending || !form.name.trim()}>
            {isPending ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <form id="rule-editor-form" className="space-y-4" onSubmit={submit} noValidate>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field label="规则名称" hint="用于告警标题与报表展示">
              <input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="例如：CPU 持续高负载" aria-label="规则名称" />
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Field label="描述">
              <input className="input" value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="规则触发条件的说明" aria-label="规则描述" />
            </Field>
          </div>
          <Field label="严重级别">
            <select className="input" value={form.severity} onChange={(e) => set("severity", e.target.value as Severity)} aria-label="严重级别">
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {s === "low" ? "低危" : s === "medium" ? "中危" : s === "high" ? "高危" : "严重"}
                </option>
              ))}
            </select>
          </Field>
          <Field label="规则类型">
            <select
              className="input"
              value={form.kind}
              onChange={(e) => {
                const kind = e.target.value;
                setForm((f) => ({ ...f, kind, condition_field: KIND_FIELDS[kind]?.[0] ?? f.condition_field }));
              }}
              aria-label="规则类型"
            >
              {Object.entries(KIND_LABELS).map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="条件字段">
            <select className="input" value={form.condition_field} onChange={(e) => set("condition_field", e.target.value)} aria-label="条件字段">
              {fields.map((f) => (
                <option key={f} value={f}>
                  {FIELD_LABELS[f] ?? f}
                </option>
              ))}
            </select>
          </Field>
          <Field label="比较符">
            <select className="input" value={form.condition_op} onChange={(e) => set("condition_op", e.target.value)} aria-label="比较符">
              {OPS.map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </select>
          </Field>
          <Field label="阈值">
            <input
              type="number"
              min={0}
              step={1}
              className="input"
              value={form.threshold}
              onChange={(e) => set("threshold", Number(e.target.value))}
              aria-label="阈值"
            />
          </Field>
          <Field label="统计窗口（秒）" hint="例如 300 = 5 分钟窗口">
            <input
              type="number"
              min={10}
              step={10}
              className="input"
              value={form.window_seconds}
              onChange={(e) => set("window_seconds", Number(e.target.value))}
              aria-label="统计窗口"
            />
          </Field>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <Toggle checked={form.enabled} onChange={(v) => set("enabled", v)} label="启用规则" />
              保存后立即启用
            </label>
          </div>
        </div>
        {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700 ring-1 ring-rose-200" role="alert">{error.message}</p>}
      </form>
    </Modal>
  );
}
