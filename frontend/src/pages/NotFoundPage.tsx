// 404 页面

import { ShieldQuestion } from "lucide-react";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-canvas-100 px-4">
      <ShieldQuestion className="h-12 w-12 text-brand-300" aria-hidden />
      <p className="text-4xl font-semibold tracking-tight text-slate-900">404</p>
      <p className="text-sm text-slate-500">页面不存在或已被移除</p>
      <Link to="/overview" className="btn-primary">
        返回总览
      </Link>
    </div>
  );
}
