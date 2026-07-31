// HostGuard 前端类型模型 —— 与 contracts/conventions.md 对齐

export type Role = "admin" | "analyst" | "viewer";
export type Severity = "low" | "medium" | "high" | "critical";
export type HostStatus = "online" | "degraded" | "offline";
export type HostSource = "real" | "simulated";
export type AlertStatus = "open" | "investigating" | "resolved" | "ignored";
export type ReportStatus = "pending" | "running" | "completed" | "failed" | "expired";
export type NotificationType = "email" | "webhook" | "wecom";

/** 结构化错误信封，见 contracts/conventions.md */
export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    request_id: string;
  };
}

/** 分页信封，见 contracts/conventions.md */
export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface User {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface Host {
  id: string;
  hostname: string;
  os: "windows" | "linux";
  os_version: string;
  architecture: string;
  status: HostStatus;
  source: HostSource;
  ip_addresses: string[];
  agent_version: string;
  last_seen_at: string | null;
  created_at: string;
  metrics?: {
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
    network_bytes_sent: number;
    network_bytes_recv: number;
    collected_at: string;
  };
  inventory?: {
    boot_time: string | null;
    processes: number;
    listening_ports: number;
  };
}

export interface Alert {
  id: string;
  host_id: string;
  hostname: string;
  rule_id: string;
  rule_name: string;
  severity: Severity;
  status: AlertStatus;
  summary: string;
  details: string | null;
  occurred_at: string;
  updated_at: string;
  assignee: string | null;
}

export interface DetectionRule {
  id: string;
  name: string;
  description: string;
  severity: Severity;
  enabled: boolean;
  kind: string;
  window_seconds: number;
  threshold: number;
  updated_at: string;
}

export interface ReportJob {
  id: string;
  title: string;
  status: ReportStatus;
  requested_by: string;
  requested_at: string;
  expires_at: string | null;
  error: string | null;
}

export interface NotificationChannel {
  id: string;
  name: string;
  type: NotificationType;
  enabled: boolean;
  target: string;
  created_at: string;
}

export interface NotificationDelivery {
  id: string;
  channel_id: string;
  channel_name: string;
  status: "pending" | "retrying" | "sent" | "failed";
  subject: string;
  attempted_at: string;
  error: string | null;
}

export interface AuditEvent {
  id: string;
  actor: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  outcome: "success" | "failure";
  detail: string | null;
  occurred_at: string;
  ip: string | null;
}

export interface DashboardSummary {
  hosts_total: number;
  hosts_online: number;
  hosts_degraded: number;
  hosts_offline: number;
  alerts_open: number;
  alerts_critical: number;
  alerts_high: number;
  alerts_today: number;
  events_today: number;
  rules_enabled: number;
  recent_alerts: Alert[];
}

export interface ProcessSnapshot {
  pid: number;
  name: string;
  username: string | null;
  started_at: string | null;
}

export interface ListeningPort {
  protocol: "tcp" | "udp";
  local_address: string;
  local_port: number;
  pid: number | null;
}

export interface HostDetail extends Host {
  process_snapshot: ProcessSnapshot[];
  listening_ports: ListeningPort[];
  file_changes: Array<{
    path: string;
    change_type: "created" | "modified" | "deleted" | "permission_changed";
    occurred_at: string;
    sha256: string | null;
    size: number | null;
  }>;
  security_events: Array<{
    event_type: string;
    severity: Severity;
    occurred_at: string;
    summary: string;
    source_ip: string | null;
    username: string | null;
  }>;
  baseline_results: Array<{
    check_id: string;
    status: "pass" | "fail" | "unavailable";
    checked_at: string;
    message: string;
  }>;
}
