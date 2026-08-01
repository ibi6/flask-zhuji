// 通知配置页：admin 配置 email/webhook 渠道并测试发送，展示投递状态列表

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Send } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import type { NotificationChannel, NotificationDelivery, NotificationType, Page } from "@/lib/types";
import {
  DeliveryStatusBadge,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  Pagination,
  QueryState,
  Toggle,
  formatTime,
} from "@/components/ui";
import { useAuth } from "@/store/auth";

const DELIVERY_PAGE_SIZE = 8;

const TYPE_OPTIONS: { value: NotificationType; label: string }[] = [
  { value: "email", label: "邮件" },
  { value: "webhook", label: "Webhook" },
  { value: "wecom", label: "企业微信" },
];

const TYPE_LABELS: Record<string, string> = {
  email: "邮件",
  webhook: "Webhook",
  wecom: "企业微信",
};

interface ChannelForm {
  name: string;
  type: NotificationType;
  target: string;
  enabled: boolean;
}

const EMPTY_FORM: ChannelForm = { name: "", type: "email", target: "", enabled: true };

export function NotificationsPage() {
  const { user } = useAuth();
  const canAccess = !user || user.role === "admin";

  const queryClient = useQueryClient();
  const [editor, setEditor] = useState<{ mode: "create" } | { mode: "edit"; channel: NotificationChannel } | null>(null);
  const [deliveryPage, setDeliveryPage] = useState(1);
  const [testMsg, setTestMsg] = useState<{ channelId: string; ok: boolean; text: string } | null>(null);

  const channelsQuery = useQuery({
    queryKey: ["notifications", "channels"],
    queryFn: () => apiGet<NotificationChannel[]>("/notifications/channels"),
    enabled: canAccess,
  });

  const deliveriesQuery = useQuery({
    queryKey: ["notifications", "deliveries", deliveryPage],
    queryFn: () =>
      apiGet<Page<NotificationDelivery>>("/notifications/deliveries", {
        query: { page: deliveryPage, page_size: DELIVERY_PAGE_SIZE },
      }),
    enabled: canAccess,
  });

  const saveMutation = useMutation({
    mutationFn: ({ form, channelId }: { form: ChannelForm; channelId?: string }) =>
      channelId
        ? apiPatch<NotificationChannel>(`/notifications/channels/${channelId}`, form)
        : apiPost<NotificationChannel>("/notifications/channels", form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications", "channels"] });
      setEditor(null);
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (channel: NotificationChannel) =>
      apiPatch<NotificationChannel>(`/notifications/channels/${channel.id}`, { enabled: !channel.enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications", "channels"] }),
  });

  const testMutation = useMutation({
    mutationFn: (channelId: string) => apiPost<NotificationDelivery>(`/notifications/channels/${channelId}/test`),
    onSuccess: (delivery) => {
      queryClient.invalidateQueries({ queryKey: ["notifications", "deliveries"] });
      setTestMsg({
        channelId: delivery.channel_id,
        ok: delivery.status !== "failed",
        text:
          delivery.status === "failed"
            ? `测试发送失败：${delivery.error ?? "未知错误"}`
            : "测试消息已发送",
      });
    },
    onError: (err: Error) => {
      setTestMsg({ channelId: testMutation.variables ?? "", ok: false, text: `测试发送失败：${err.message}` });
    },
  });

  if (!canAccess) {
    return <Navigate to="/overview" replace />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="通知配置"
        description="管理告警通知渠道、测试发送并查看投递状态"
        actions={
          <button type="button" className="btn-primary" onClick={() => setEditor({ mode: "create" })}>
            <Plus className="h-4 w-4" aria-hidden />
            新建渠道
          </button>
        }
      />

      {/* 渠道配置 */}
      <div className="card overflow-hidden p-0">
        <QueryState data={channelsQuery.data} isPending={channelsQuery.isPending} error={channelsQuery.error} onRetry={() => channelsQuery.refetch()}>
          {(list) =>
            list.length === 0 ? (
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
                      <th className="px-5 py-3 text-right font-medium">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {list.map((ch) => (
                      <tr key={ch.id} className="transition hover:bg-slate-50/60">
                        <td className="px-5 py-3 font-medium text-slate-800">{ch.name}</td>
                        <td className="px-5 py-3">
                          <span className="inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600">
                            {TYPE_LABELS[ch.type] ?? ch.type}
                          </span>
                        </td>
                        <td className="max-w-xs truncate px-5 py-3 font-mono text-xs text-slate-500" title={ch.target}>
                          {ch.target}
                        </td>
                        <td className="px-5 py-3">
                          <Toggle
                            checked={ch.enabled}
                            onChange={() => toggleMutation.mutate(ch)}
                            disabled={toggleMutation.isPending}
                            label={ch.enabled ? "禁用渠道" : "启用渠道"}
                          />
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-400">{formatTime(ch.created_at)}</td>
                        <td className="px-5 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              type="button"
                              className="btn-secondary !px-2.5 !py-1 text-xs"
                              disabled={testMutation.isPending}
                              onClick={() => testMutation.mutate(ch.id)}
                            >
                              <Send className="h-3.5 w-3.5" aria-hidden />
                              测试
                            </button>
                            <button
                              type="button"
                              className="btn-secondary !px-2.5 !py-1 text-xs"
                              onClick={() => setEditor({ mode: "edit", channel: ch })}
                            >
                              编辑
                            </button>
                          </div>
                          {testMsg && testMsg.channelId === ch.id && (
                            <p className={`mt-1 text-right text-xs ${testMsg.ok ? "text-emerald-600" : "text-rose-600"}`} role="status">
                              {testMsg.text}
                            </p>
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

      {/* 投递记录 */}
      <h2 className="mb-3 mt-8 text-sm font-semibold text-slate-800">投递记录</h2>
      <div className="card overflow-hidden p-0">
        <QueryState data={deliveriesQuery.data} isPending={deliveriesQuery.isPending} error={deliveriesQuery.error} onRetry={() => deliveriesQuery.refetch()}>
          {(dPage) =>
            dPage.items.length === 0 ? (
              <EmptyState title="暂无投递记录" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                      <th className="px-5 py-3 font-medium">主题</th>
                      <th className="px-5 py-3 font-medium">渠道</th>
                      <th className="px-5 py-3 font-medium">状态</th>
                      <th className="px-5 py-3 font-medium">尝试时间</th>
                      <th className="px-5 py-3 font-medium">错误</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {dPage.items.map((d) => (
                      <tr key={d.id} className="transition hover:bg-slate-50/60">
                        <td className="px-5 py-3 font-medium text-slate-800">{d.subject}</td>
                        <td className="px-5 py-3 text-slate-600">{d.channel_name}</td>
                        <td className="px-5 py-3">
                          <DeliveryStatusBadge status={d.status} />
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-400">{formatTime(d.attempted_at)}</td>
                        <td className="max-w-xs truncate px-5 py-3 text-xs text-rose-500" title={d.error ?? ""}>
                          {d.error ?? "—"}
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

      {deliveriesQuery.data && deliveriesQuery.data.total > DELIVERY_PAGE_SIZE && (
        <Pagination
          page={deliveriesQuery.data.page}
          pageSize={deliveriesQuery.data.page_size}
          total={deliveriesQuery.data.total}
          onChange={setDeliveryPage}
        />
      )}

      {editor && (
        <ChannelModal
          initial={editor.mode === "edit" ? { name: editor.channel.name, type: editor.channel.type, target: editor.channel.target, enabled: editor.channel.enabled } : EMPTY_FORM}
          isEdit={editor.mode === "edit"}
          isPending={saveMutation.isPending}
          error={saveMutation.error}
          onClose={() => setEditor(null)}
          onSave={(form) => saveMutation.mutate({ form, channelId: editor.mode === "edit" ? editor.channel.id : undefined })}
        />
      )}
    </div>
  );
}

function ChannelModal({
  initial,
  isEdit,
  isPending,
  error,
  onClose,
  onSave,
}: {
  initial: ChannelForm;
  isEdit: boolean;
  isPending: boolean;
  error: Error | null;
  onClose: () => void;
  onSave: (form: ChannelForm) => void;
}) {
  const [form, setForm] = useState<ChannelForm>(initial);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.target.trim()) return;
    onSave({ ...form, name: form.name.trim(), target: form.target.trim() });
  };

  return (
    <Modal
      title={isEdit ? "编辑渠道" : "新建通知渠道"}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={isPending}>
            取消
          </button>
          <button type="submit" form="channel-form" className="btn-primary" disabled={isPending || !form.name.trim() || !form.target.trim()}>
            {isPending ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <form id="channel-form" className="space-y-4" onSubmit={submit} noValidate>
        <Field label="渠道名称">
          <input className="input" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="例如：安全值班邮箱" aria-label="渠道名称" />
        </Field>
        <Field label="渠道类型">
          <select className="input" value={form.type} onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as NotificationType }))} aria-label="渠道类型">
            {TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="目标" hint={form.type === "email" ? "接收告警的邮箱地址" : "Webhook URL（企业微信请使用群机器人 Webhook）"}>
          <input
            className="input font-mono"
            value={form.target}
            onChange={(e) => setForm((f) => ({ ...f, target: e.target.value }))}
            placeholder={form.type === "email" ? "sec-oncall@example.com" : "https://…"}
            aria-label="目标地址"
          />
        </Field>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <Toggle checked={form.enabled} onChange={(v) => setForm((f) => ({ ...f, enabled: v }))} label="启用渠道" />
          保存后启用
        </label>
        {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700 ring-1 ring-rose-200" role="alert">{error.message}</p>}
      </form>
    </Modal>
  );
}
