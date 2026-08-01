// HostGuard 前端类型模型 —— 与 contracts/conventions.md 对齐

export type Role = "admin" | "analyst" | "viewer";
export type Severity = "low" | "medium" | "high" | "critical";
export type HostStatus = "online" | "degraded" | "offline";
export type HostSource = "real" | "simulated";
export type AlertStatus = "open" | "investigating" | "resolved" | "ignored";
export type ReportStatus = "pending" | "running" | "completed" | "failed" | "expired";
export type NotificationType = "email" | "webhook" | "wecom";
export type DeliveryStatus = "pending" | "retrying" | "sent" | "failed";

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
  /** 触发条件的指标/事件字段，例如 cpu_percent、login_failures */
  condition_field: string;
  /** 触发条件比较符，例如 >=、>、<、== */
  condition_op: string;
  window_seconds: number;
  threshold: number;
  updated_at: string;
}

export interface ReportJob {
  id: string;
  title: string;
  status: ReportStatus;
  /** 报告范围，例如 all_hosts / alerts / hosts / baseline */
  scope: string;
  /** 报告类型，例如 summary / alert_analysis / baseline_compliance */
  report_type: string;
  /** 导出格式，例如 pdf / csv / html */
  format: string;
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
  status: DeliveryStatus;
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

export interface RiskTrendPoint {
  /** 日期标签，例如 "07-20" 或完整 ISO 日期 */
  date: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
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
  /** 按严重级别统计的真实告警分布 */
  alert_distribution: Record<Severity, number>;
  /** 风险趋势（近 N 天每日告警量） */
  risk_trend: RiskTrendPoint[];
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

/** 遥测时间序列点，用于真实趋势图 */
export interface TelemetryPoint {
  collected_at: string;
  cpu_percent: number;
  memory_percent: number;
  network_bytes_sent: number;
  network_bytes_recv: number;
}

/** 告警状态流转记录 */
export interface AlertTransition {
  id: string;
  from_status: AlertStatus;
  to_status: AlertStatus;
  comment: string | null;
  actor: string;
  occurred_at: string;
}

/** 告警详情：列表项 + 状态历史 */
export interface AlertDetail extends Alert {
  transitions: AlertTransition[];
}

export interface HostDetail extends Host {
  telemetry: TelemetryPoint[];
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
