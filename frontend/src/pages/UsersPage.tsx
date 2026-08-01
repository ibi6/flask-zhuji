// 用户管理页：admin 专用 — 新增 / 编辑 / 禁用 / 删除

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Search, Trash2, UserX, UserCheck } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { ApiError, apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";
import type { Page, Role, User } from "@/lib/types";
import {
  EmptyState,
  Field,
  Modal,
  Pagination,
  PageHeader,
  QueryState,
  RoleBadge,
  Toggle,
  formatTime,
} from "@/components/ui";
import { useAuth } from "@/store/auth";

const PAGE_SIZE = 20;

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: "admin", label: "管理员" },
  { value: "analyst", label: "分析员" },
  { value: "viewer", label: "只读用户" },
];

interface CreateForm {
  username: string;
  email: string;
  password: string;
  display_name: string;
  role: Role;
}

const EMPTY_CREATE: CreateForm = {
  username: "",
  email: "",
  password: "",
  display_name: "",
  role: "viewer",
};

function validatePassword(password: string): string | null {
  if (password.length < 12) return "密码至少 12 位";
  if (!/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/\d/.test(password)) {
    return "密码须包含大写、小写字母和数字";
  }
  return null;
}

export function UsersPage() {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateForm>(EMPTY_CREATE);
  const [createError, setCreateError] = useState<string | null>(null);
  const [editUser, setEditUser] = useState<User | null>(null);
  const [deleteUser, setDeleteUser] = useState<User | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const canAccess = !currentUser || currentUser.role === "admin";

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["users", page, search],
    queryFn: () =>
      apiGet<Page<User>>("/users", {
        query: { page, page_size: PAGE_SIZE, search: search || undefined },
      }),
    enabled: canAccess,
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateForm) =>
      apiPost<{ user: User }>("/users", {
        username: payload.username.trim(),
        email: payload.email.trim(),
        password: payload.password,
        role: payload.role,
        ...(payload.display_name.trim() ? { display_name: payload.display_name.trim() } : {}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setCreateOpen(false);
      setCreateForm(EMPTY_CREATE);
      setCreateError(null);
    },
    onError: (err) => {
      setCreateError(err instanceof ApiError ? err.message : "创建失败");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: { role?: Role; is_active?: boolean } }) =>
      apiPatch<{ user: User }>(`/users/${id}`, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setEditUser(null);
      setFormError(null);
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "更新失败");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiDelete(`/users/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setDeleteUser(null);
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "删除失败");
    },
  });

  if (!canAccess) {
    return <Navigate to="/overview" replace />;
  }

  const handleCreate = (e: FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    if (!createForm.username.trim() || !createForm.email.trim() || !createForm.password) {
      setCreateError("请填写必填项");
      return;
    }
    const pwdErr = validatePassword(createForm.password);
    if (pwdErr) {
      setCreateError(pwdErr);
      return;
    }
    createMutation.mutate(createForm);
  };

  const isSelf = (u: User) => currentUser?.id === u.id;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="用户管理"
        description="管理平台用户与角色，支持新增、编辑、启用/禁用"
        actions={
          <button type="button" className="btn-primary" onClick={() => { setCreateOpen(true); setCreateError(null); }}>
            <Plus className="h-4 w-4" aria-hidden />
            新增用户
          </button>
        }
      />

      <div className="mb-4 flex items-center gap-3">
        <div className="relative max-w-xs flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: "var(--input-icon)" }} aria-hidden />
          <input
            type="search"
            className="input pl-9"
            placeholder="搜索用户名或邮箱…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            aria-label="搜索用户"
          />
        </div>
      </div>

      <div className="card overflow-hidden p-0">
        <QueryState data={data} isPending={isPending} error={error} onRetry={() => refetch()}>
          {(pageData) =>
            pageData.items.length === 0 ? (
              <EmptyState title={search ? "未找到用户" : "暂无用户"} description={search ? "尝试更换关键词" : "点击右上角新增用户"} />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs" style={{ borderColor: "var(--divider)", color: "var(--muted)" }}>
                      <th className="px-5 py-3 font-medium">用户名</th>
                      <th className="px-5 py-3 font-medium">显示名</th>
                      <th className="px-5 py-3 font-medium">邮箱</th>
                      <th className="px-5 py-3 font-medium">角色</th>
                      <th className="px-5 py-3 font-medium">状态</th>
                      <th className="px-5 py-3 font-medium">最后登录</th>
                      <th className="px-5 py-3 font-medium">创建时间</th>
                      <th className="px-5 py-3 text-right font-medium">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y" style={{ borderColor: "var(--divider)" }}>
                    {pageData.items.map((u) => (
                      <tr key={u.id} className="transition hover:bg-[var(--table-hover)]">
                        <td className="px-5 py-3 font-mono">{u.username}</td>
                        <td className="px-5 py-3 font-medium">{u.display_name}</td>
                        <td className="px-5 py-3 text-xs" style={{ color: "var(--muted)" }}>
                          {u.email ?? "—"}
                        </td>
                        <td className="px-5 py-3">
                          <RoleBadge role={u.role} />
                        </td>
                        <td className="px-5 py-3">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${
                              u.is_active
                                ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                                : "bg-slate-100 text-slate-500 ring-slate-200"
                            }`}
                          >
                            {u.is_active ? "启用" : "禁用"}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-xs" style={{ color: "var(--muted)" }}>
                          {formatTime(u.last_login_at)}
                        </td>
                        <td className="px-5 py-3 text-xs" style={{ color: "var(--muted)" }}>
                          {formatTime(u.created_at)}
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex justify-end gap-1">
                            <button
                              type="button"
                              className="btn-secondary !px-2 !py-1 text-xs"
                              disabled={isSelf(u)}
                              title={isSelf(u) ? "不能编辑自己的账号" : "编辑"}
                              onClick={() => { setEditUser(u); setFormError(null); }}
                            >
                              <Pencil className="h-3 w-3" aria-hidden />
                              编辑
                            </button>
                            <button
                              type="button"
                              className="btn-secondary !px-2 !py-1 text-xs"
                              disabled={isSelf(u) || updateMutation.isPending}
                              title={isSelf(u) ? "不能禁用自己" : u.is_active ? "禁用" : "启用"}
                              onClick={() =>
                                updateMutation.mutate({ id: u.id, patch: { is_active: !u.is_active } })
                              }
                            >
                              {u.is_active ? (
                                <UserX className="h-3 w-3" aria-hidden />
                              ) : (
                                <UserCheck className="h-3 w-3" aria-hidden />
                              )}
                              {u.is_active ? "禁用" : "启用"}
                            </button>
                            <button
                              type="button"
                              className="btn-danger !px-2 !py-1 text-xs"
                              disabled={isSelf(u)}
                              title={isSelf(u) ? "不能删除自己" : "删除（软禁用）"}
                              onClick={() => { setDeleteUser(u); setFormError(null); }}
                            >
                              <Trash2 className="h-3 w-3" aria-hidden />
                              删除
                            </button>
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

      {createOpen && (
        <Modal
          title="新增用户"
          onClose={() => setCreateOpen(false)}
          footer={
            <>
              <button type="button" className="btn-secondary" onClick={() => setCreateOpen(false)}>
                取消
              </button>
              <button type="submit" form="create-user-form" className="btn-primary" disabled={createMutation.isPending}>
                {createMutation.isPending ? "创建中…" : "创建"}
              </button>
            </>
          }
        >
          <form id="create-user-form" onSubmit={handleCreate} className="space-y-4">
            <Field label="用户名" hint="3~64 字符，登录凭据">
              <input
                className="input"
                value={createForm.username}
                onChange={(e) => setCreateForm((f) => ({ ...f, username: e.target.value }))}
                placeholder="zhang.san"
                autoComplete="off"
              />
            </Field>
            <Field label="显示名">
              <input
                className="input"
                value={createForm.display_name}
                onChange={(e) => setCreateForm((f) => ({ ...f, display_name: e.target.value }))}
                placeholder="张三"
              />
            </Field>
            <Field label="邮箱">
              <input
                type="email"
                className="input"
                value={createForm.email}
                onChange={(e) => setCreateForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="user@example.com"
              />
            </Field>
            <Field label="初始密码" hint="至少 12 位，含大小写字母与数字">
              <input
                type="password"
                className="input"
                value={createForm.password}
                onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
                autoComplete="new-password"
              />
            </Field>
            <Field label="角色">
              <select
                className="input"
                value={createForm.role}
                onChange={(e) => setCreateForm((f) => ({ ...f, role: e.target.value as Role }))}
              >
                {ROLE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </Field>
            {createError && (
              <p className="rounded-xl px-3 py-2 text-xs text-rose-700 ring-1 ring-rose-200" role="alert">
                {createError}
              </p>
            )}
          </form>
        </Modal>
      )}

      {editUser && (
        <Modal
          title={`编辑用户 · ${editUser.username}`}
          onClose={() => setEditUser(null)}
          footer={
            <>
              <button type="button" className="btn-secondary" onClick={() => setEditUser(null)}>取消</button>
              <button
                type="button"
                className="btn-primary"
                disabled={updateMutation.isPending}
                onClick={() =>
                  updateMutation.mutate({
                    id: editUser.id,
                    patch: { role: editUser.role, is_active: editUser.is_active },
                  })
                }
              >
                保存
              </button>
            </>
          }
        >
          <div className="space-y-4">
            <Field label="角色">
              <select
                className="input"
                value={editUser.role}
                onChange={(e) => setEditUser({ ...editUser, role: e.target.value as Role })}
              >
                {ROLE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </Field>
            <div className="flex items-center justify-between">
              <span className="text-sm" style={{ color: "var(--ink-soft)" }}>账号启用</span>
              <Toggle
                checked={editUser.is_active}
                onChange={(v) => setEditUser({ ...editUser, is_active: v })}
                label="账号启用"
              />
            </div>
            {formError && <p className="text-xs text-rose-600" role="alert">{formError}</p>}
          </div>
        </Modal>
      )}

      {deleteUser && (
        <Modal
          title="确认删除用户"
          onClose={() => setDeleteUser(null)}
          footer={
            <>
              <button type="button" className="btn-secondary" onClick={() => setDeleteUser(null)}>取消</button>
              <button
                type="button"
                className="btn-danger"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate(deleteUser.id)}
              >
                {deleteMutation.isPending ? "处理中…" : "确认删除"}
              </button>
            </>
          }
        >
          <p className="text-sm" style={{ color: "var(--ink-soft)" }}>
            将禁用用户 <span className="font-mono font-semibold">{deleteUser.username}</span> 并撤销其所有会话。此操作与后端软删除一致，可稍后重新启用。
          </p>
          {formError && <p className="mt-3 text-xs text-rose-600" role="alert">{formError}</p>}
        </Modal>
      )}
    </div>
  );
}
