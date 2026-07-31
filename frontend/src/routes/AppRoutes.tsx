// 应用路由

import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { AlertsPage } from "@/pages/AlertsPage";
import { AuditPage } from "@/pages/AuditPage";
import { HostDetailPage } from "@/pages/HostDetailPage";
import { HostsPage } from "@/pages/HostsPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotificationsPage } from "@/pages/NotificationsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OverviewPage } from "@/pages/OverviewPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { RulesPage } from "@/pages/RulesPage";
import { UsersPage } from "@/pages/UsersPage";
import { GuestRoute, ProtectedRoute, RoleRoute } from "@/routes/guards";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<GuestRoute />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/hosts" element={<HostsPage />} />
          <Route path="/hosts/:hostId" element={<HostDetailPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/rules" element={<RulesPage />} />
          <Route element={<RoleRoute minRole="analyst" />}>
            <Route path="/reports" element={<ReportsPage />} />
          </Route>
          <Route element={<RoleRoute minRole="admin" />}>
            <Route path="/notifications" element={<NotificationsPage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/audit" element={<AuditPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
