// 本地 mock 适配器 —— 仅供显式开发模式使用（VITE_USE_MOCK === "true" 才开启）。
// 所有数据均为模拟数据，绝不可伪装为真实遥测；界面会常驻"开发模式"标注。
// 默认走真实 API：mock 与真实数据绝不混用。

import type {
  Alert,
  AlertDetail,
  AlertTransition,
  AuditEvent,
  DashboardSummary,
  DetectionRule,
  Host,
  HostDetail,
  NotificationChannel,
  NotificationDelivery,
  Page,
  ReportJob,
  TelemetryPoint,
  User,
} from "./types";

export const MOCK_ACTIVE = import.meta.env.VITE_USE_MOCK === "true";

export interface CurrentUserLike {
  id: string;
  username: string;
  display_name: string;
  role: "admin" | "analyst" | "viewer";
}

function uuid(seed: number): string {
  const hex = (n: number) => Math.abs(n).toString(16).padStart(8, "0").slice(-8);
  return `${hex(seed)}-${hex(seed + 1)}-${hex(seed + 2)}-${hex(seed + 3)}-${hex(seed + 4)}`;
}

const now = Date.now();
const iso = (offsetMin: number) => new Date(now - offsetMin * 60_000).toISOString();
const delay = (ms = 150) => new Promise((r) => setTimeout(r, ms));
let mockSeq = 9000;

/** 确定性伪随机（基于种子），避免每次渲染波动 */
function seeded(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff;
  };
}

// ---- 模拟数据 ----

export const mockUsers: User[] = [
  { id: uuid(100), username: "admin", display_name: "安全管理员", role: "admin", is_active: true, created_at: iso(60 * 24 * 90), last_login_at: iso(5) },
  { id: uuid(110), username: "li.wei", display_name: "李伟", role: "analyst", is_active: true, created_at: iso(60 * 24 * 60), last_login_at: iso(35) },
  { id: uuid(120), username: "zhang.yu", display_name: "张雨", role: "analyst", is_active: true, created_at: iso(60 * 24 * 45), last_login_at: iso(200) },
  { id: uuid(130), username: "wang.fang", display_name: "王芳", role: "viewer", is_active: true, created_at: iso(60 * 24 * 30), last_login_at: iso(60 * 8) },
  { id: uuid(140), username: "chen.jie", display_name: "陈杰", role: "viewer", is_active: false, created_at: iso(60 * 24 * 20), last_login_at: iso(60 * 24 * 9) },
];

export const mockHosts: Host[] = [
  { id: uuid(200), hostname: "web-prod-01", os: "linux", os_version: "Ubuntu 22.04.4 LTS", architecture: "x86_64", status: "online", source: "real", ip_addresses: ["10.0.1.11", "172.16.0.11"], agent_version: "0.1.0", last_seen_at: iso(1), created_at: iso(60 * 24 * 60), metrics: { cpu_percent: 23.5, memory_percent: 41.2, disk_percent: 55.1, network_bytes_sent: 3_412_889_201, network_bytes_recv: 12_883_119_004, collected_at: iso(1) }, inventory: { boot_time: iso(60 * 24 * 3), processes: 128, listening_ports: 9 } },
  { id: uuid(210), hostname: "web-prod-02", os: "linux", os_version: "Ubuntu 22.04.4 LTS", architecture: "x86_64", status: "online", source: "real", ip_addresses: ["10.0.1.12"], agent_version: "0.1.0", last_seen_at: iso(1), created_at: iso(60 * 24 * 60), metrics: { cpu_percent: 31.2, memory_percent: 38.9, disk_percent: 52.4, network_bytes_sent: 2_988_100_452, network_bytes_recv: 9_112_882_000, collected_at: iso(1) }, inventory: { boot_time: iso(60 * 24 * 3), processes: 121, listening_ports: 8 } },
  { id: uuid(220), hostname: "db-mysql-01", os: "linux", os_version: "CentOS Stream 9", architecture: "x86_64", status: "degraded", source: "real", ip_addresses: ["10.0.2.21"], agent_version: "0.1.0", last_seen_at: iso(2), created_at: iso(60 * 24 * 58), metrics: { cpu_percent: 78.4, memory_percent: 86.2, disk_percent: 91.7, network_bytes_sent: 18_201_003_221, network_bytes_recv: 21_400_188_020, collected_at: iso(2) }, inventory: { boot_time: iso(60 * 24 * 20), processes: 96, listening_ports: 4 } },
  { id: uuid(230), hostname: "app-pay-01", os: "linux", os_version: "Ubuntu 20.04.6 LTS", architecture: "x86_64", status: "online", source: "real", ip_addresses: ["10.0.3.31"], agent_version: "0.1.0", last_seen_at: iso(1), created_at: iso(60 * 24 * 55), metrics: { cpu_percent: 12.3, memory_percent: 33.1, disk_percent: 47.6, network_bytes_sent: 5_001_220_871, network_bytes_recv: 7_821_000_112, collected_at: iso(1) }, inventory: { boot_time: iso(60 * 24 * 6), processes: 88, listening_ports: 6 } },
  { id: uuid(240), hostname: "win-dc-01", os: "windows", os_version: "Windows Server 2022", architecture: "AMD64", status: "offline", source: "real", ip_addresses: ["10.0.0.5"], agent_version: "0.1.0", last_seen_at: iso(60 * 5), created_at: iso(60 * 24 * 45), inventory: { boot_time: iso(60 * 24 * 12), processes: 0, listening_ports: 0 } },
  { id: uuid(250), hostname: "win-terminal-02", os: "windows", os_version: "Windows 11 Enterprise", architecture: "AMD64", status: "online", source: "real", ip_addresses: ["10.0.4.42"], agent_version: "0.1.0", last_seen_at: iso(1), created_at: iso(60 * 24 * 30), metrics: { cpu_percent: 9.8, memory_percent: 61.4, disk_percent: 78.2, network_bytes_sent: 892_100_552, network_bytes_recv: 2_101_882_331, collected_at: iso(1) }, inventory: { boot_time: iso(60 * 24 * 1), processes: 210, listening_ports: 14 } },
  { id: uuid(260), hostname: "lab-node-01", os: "linux", os_version: "Rocky Linux 9.3", architecture: "x86_64", status: "online", source: "simulated", ip_addresses: ["192.168.50.10"], agent_version: "0.2.0-dev", last_seen_at: iso(1), created_at: iso(60 * 24 * 5), metrics: { cpu_percent: 3.2, memory_percent: 18.7, disk_percent: 22.4, network_bytes_sent: 12_800_221, network_bytes_recv: 33_100_119, collected_at: iso(1) }, inventory: { boot_time: iso(60 * 24 * 5), processes: 45, listening_ports: 3 } },
  { id: uuid(270), hostname: "lab-node-02", os: "linux", os_version: "Rocky Linux 9.3", architecture: "x86_64", status: "online", source: "simulated", ip_addresses: ["192.168.50.11"], agent_version: "0.2.0-dev", last_seen_at: iso(1), created_at: iso(60 * 24 * 5), metrics: { cpu_percent: 6.7, memory_percent: 24.3, disk_percent: 31.8, network_bytes_sent: 9_900_221, network_bytes_recv: 20_400_119, collected_at: iso(1) }, inventory: { boot_time: iso(60 * 24 * 5), processes: 52, listening_ports: 5 } },
];

export const mockRules: DetectionRule[] = [
  { id: uuid(300), name: "CPU 持续高负载", description: "CPU 使用率超过 85% 且持续 5 分钟", severity: "high", enabled: true, kind: "metric", condition_field: "cpu_percent", condition_op: ">=", window_seconds: 300, threshold: 85, updated_at: iso(60 * 24 * 3) },
  { id: uuid(310), name: "内存接近耗尽", description: "内存使用率超过 90%", severity: "high", enabled: true, kind: "metric", condition_field: "memory_percent", condition_op: ">=", window_seconds: 300, threshold: 90, updated_at: iso(60 * 24 * 3) },
  { id: uuid(320), name: "磁盘空间告警", description: "磁盘使用率超过 85%", severity: "medium", enabled: true, kind: "metric", condition_field: "disk_percent", condition_op: ">=", window_seconds: 600, threshold: 85, updated_at: iso(60 * 24 * 3) },
  { id: uuid(330), name: "异常登录尝试", description: "单台主机 10 分钟内超过 5 次登录失败", severity: "critical", enabled: true, kind: "event", condition_field: "login_failures", condition_op: ">=", window_seconds: 600, threshold: 5, updated_at: iso(60 * 24 * 2) },
  { id: uuid(340), name: "敏感文件变更", description: "/etc/passwd、/etc/shadow 等关键文件被修改", severity: "critical", enabled: true, kind: "fim", condition_field: "file_changes", condition_op: ">=", window_seconds: 60, threshold: 1, updated_at: iso(60 * 24 * 2) },
  { id: uuid(350), name: "新开放高危端口", description: "出现新的 22/3389/3306 等端口监听", severity: "medium", enabled: false, kind: "port", condition_field: "high_risk_port", condition_op: ">=", window_seconds: 600, threshold: 1, updated_at: iso(60 * 24 * 6) },
  { id: uuid(360), name: "基线合规项失败", description: "安全基线检查出现失败项", severity: "medium", enabled: true, kind: "baseline", condition_field: "baseline_fails", condition_op: ">=", window_seconds: 86400, threshold: 1, updated_at: iso(60 * 24 * 1) },
];

export const mockAlerts: Alert[] = [
  { id: uuid(400), host_id: uuid(220), hostname: "db-mysql-01", rule_id: uuid(310), rule_name: "内存接近耗尽", severity: "critical", status: "open", summary: "内存使用率达 86.2%，接近阈值 90%", details: "db-mysql-01 内存持续攀升，当前占用 86.2%，需检查慢查询与连接数。", occurred_at: iso(12), updated_at: iso(12), assignee: null },
  { id: uuid(401), host_id: uuid(220), hostname: "db-mysql-01", rule_id: uuid(320), rule_name: "磁盘空间告警", severity: "high", status: "investigating", summary: "磁盘使用率 91.7%，超过阈值 85%", details: "/data 分区使用率达 91.7%，建议清理 binlog 与归档日志。", occurred_at: iso(45), updated_at: iso(30), assignee: "li.wei" },
  { id: uuid(402), host_id: uuid(230), hostname: "app-pay-01", rule_id: uuid(330), rule_name: "异常登录尝试", severity: "critical", status: "open", summary: "10 分钟内 12 次 SSH 登录失败", details: "来源 IP 203.0.113.77 对 root 账号连续尝试登录。", occurred_at: iso(80), updated_at: iso(80), assignee: null },
  { id: uuid(403), host_id: uuid(240), hostname: "win-dc-01", rule_id: uuid(340), rule_name: "敏感文件变更", severity: "high", status: "resolved", summary: "C:\\Windows\\System32\\drivers\\etc\\hosts 被修改", details: "文件被第三方脚本修改，已确认是计划内变更。", occurred_at: iso(60 * 26), updated_at: iso(60 * 25), assignee: "zhang.yu" },
  { id: uuid(404), host_id: uuid(200), hostname: "web-prod-01", rule_id: uuid(330), rule_name: "异常登录尝试", severity: "medium", status: "resolved", summary: "10 分钟内 6 次登录失败", details: "排查为运维批量脚本使用过期密钥，非攻击行为。", occurred_at: iso(60 * 30), updated_at: iso(60 * 29), assignee: "li.wei" },
  { id: uuid(405), host_id: uuid(250), hostname: "win-terminal-02", rule_id: uuid(360), rule_name: "基线合规项失败", severity: "medium", status: "open", summary: "2 项基线检查失败", details: "密码策略与自动更新未达标。", occurred_at: iso(60 * 3), updated_at: iso(60 * 3), assignee: null },
  { id: uuid(406), host_id: uuid(210), hostname: "web-prod-02", rule_id: uuid(300), rule_name: "CPU 持续高负载", severity: "high", status: "investigating", summary: "CPU 峰值达 92% 后回落至 31.2%", details: "高峰期 CPU 冲高后回落，持续观察。", occurred_at: iso(60 * 5), updated_at: iso(60 * 4), assignee: "zhang.yu" },
  { id: uuid(407), host_id: uuid(260), hostname: "lab-node-01", rule_id: uuid(330), rule_name: "异常登录尝试", severity: "low", status: "ignored", summary: "模拟环境批量任务登录失败", details: "模拟数据，已忽略。", occurred_at: iso(60 * 50), updated_at: iso(60 * 49), assignee: "admin" },
];

export const mockReports: ReportJob[] = [
  { id: uuid(500), title: "7 月安全态势周报", status: "completed", scope: "all_hosts", report_type: "summary", format: "pdf", requested_by: "admin", requested_at: iso(60 * 24 * 2), expires_at: iso(60 * 24 * 12), error: null },
  { id: uuid(501), title: "全量主机基线合规报告", status: "running", scope: "baseline", report_type: "baseline_compliance", format: "csv", requested_by: "li.wei", requested_at: iso(30), expires_at: null, error: null },
  { id: uuid(502), title: "告警统计月报", status: "pending", scope: "alerts", report_type: "alert_analysis", format: "html", requested_by: "zhang.yu", requested_at: iso(5), expires_at: null, error: null },
  { id: uuid(503), title: "异常登录专项分析", status: "failed", scope: "alerts", report_type: "alert_analysis", format: "pdf", requested_by: "li.wei", requested_at: iso(60 * 24 * 1), expires_at: null, error: "导出阶段超时" },
  { id: uuid(504), title: "季度风险清单", status: "expired", scope: "all_hosts", report_type: "summary", format: "pdf", requested_by: "admin", requested_at: iso(60 * 24 * 40), expires_at: iso(60 * 24 * 10), error: null },
];

export const mockChannels: NotificationChannel[] = [
  { id: uuid(600), name: "安全值班邮箱", type: "email", enabled: true, target: "sec-oncall@example.com", created_at: iso(60 * 24 * 50) },
  { id: uuid(601), name: "企微告警群", type: "wecom", enabled: true, target: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=****", created_at: iso(60 * 24 * 50) },
  { id: uuid(602), name: "应急 Webhook", type: "webhook", enabled: false, target: "https://hooks.example.com/hostguard", created_at: iso(60 * 24 * 20) },
];

export const mockDeliveries: NotificationDelivery[] = [
  { id: uuid(610), channel_id: uuid(601), channel_name: "企微告警群", status: "sent", subject: "【HostGuard】高危告警：磁盘使用率超限", attempted_at: iso(44), error: null },
  { id: uuid(611), channel_id: uuid(600), channel_name: "安全值班邮箱", status: "sent", subject: "【HostGuard】严重告警：异常登录尝试", attempted_at: iso(79), error: null },
  { id: uuid(612), channel_id: uuid(602), channel_name: "应急 Webhook", status: "failed", subject: "【HostGuard】严重告警：内存耗尽", attempted_at: iso(11), error: "连接超时" },
  { id: uuid(613), channel_id: uuid(601), channel_name: "企微告警群", status: "retrying", subject: "【HostGuard】基线检查失败", attempted_at: iso(3), error: null },
];

export const mockAudit: AuditEvent[] = [
  { id: uuid(700), actor: "admin", action: "user.create", resource_type: "user", resource_id: uuid(140), outcome: "success", detail: "创建用户 chen.jie（viewer）", occurred_at: iso(60 * 24 * 20), ip: "10.0.0.2" },
  { id: uuid(701), actor: "admin", action: "rule.update", resource_type: "rule", resource_id: uuid(350), outcome: "success", detail: "禁用规则：新开放高危端口", occurred_at: iso(60 * 24 * 6), ip: "10.0.0.2" },
  { id: uuid(702), actor: "li.wei", action: "alert.transition", resource_type: "alert", resource_id: uuid(401), outcome: "success", detail: "告警状态 open → investigating", occurred_at: iso(30), ip: "10.0.0.3" },
  { id: uuid(703), actor: "zhang.yu", action: "report.create", resource_type: "report", resource_id: uuid(502), outcome: "success", detail: "创建报告：告警统计月报", occurred_at: iso(5), ip: "10.0.0.4" },
  { id: uuid(704), actor: "unknown", action: "auth.login", resource_type: "session", resource_id: null, outcome: "failure", detail: "登录失败：账号不存在（adminx）", occurred_at: iso(60 * 2), ip: "203.0.113.77" },
  { id: uuid(705), actor: "li.wei", action: "alert.transition", resource_type: "alert", resource_id: uuid(406), outcome: "success", detail: "告警状态 open → investigating", occurred_at: iso(60 * 4), ip: "10.0.0.3" },
];

// ---- 由静态数据派生：告警状态历史 ----

function transitionsFor(alert: Alert): AlertTransition[] {
  switch (alert.status) {
    case "resolved":
      return [
        { id: uuid(800 + mockAlerts.indexOf(alert) * 10), from_status: "open", to_status: "investigating", comment: "开始排查", actor: alert.assignee ?? "li.wei", occurred_at: iso(60 * 27) },
        { id: uuid(801 + mockAlerts.indexOf(alert) * 10), from_status: "investigating", to_status: "resolved", comment: "确认安全，关闭告警", actor: alert.assignee ?? "li.wei", occurred_at: iso(60 * 25) },
      ];
    case "ignored":
      return [
        { id: uuid(810 + mockAlerts.indexOf(alert) * 10), from_status: "open", to_status: "ignored", comment: "误报，忽略", actor: alert.assignee ?? "admin", occurred_at: iso(60 * 49) },
      ];
    case "investigating":
      return [
        { id: uuid(820 + mockAlerts.indexOf(alert) * 10), from_status: "open", to_status: "investigating", comment: "开始排查", actor: alert.assignee ?? "li.wei", occurred_at: iso(60 * 24) },
      ];
    default:
      return [];
  }
}

// ---- 派生 dashboard 数据 ----

export const mockDashboard: DashboardSummary = {
  hosts_total: mockHosts.length,
  hosts_online: mockHosts.filter((h) => h.status === "online").length,
  hosts_degraded: mockHosts.filter((h) => h.status === "degraded").length,
  hosts_offline: mockHosts.filter((h) => h.status === "offline").length,
  alerts_open: mockAlerts.filter((a) => a.status === "open").length,
  alerts_critical: mockAlerts.filter((a) => a.severity === "critical").length,
  alerts_high: mockAlerts.filter((a) => a.severity === "high").length,
  alerts_today: 8,
  events_today: 1243,
  rules_enabled: mockRules.filter((r) => r.enabled).length,
  alert_distribution: {
    critical: mockAlerts.filter((a) => a.severity === "critical").length,
    high: mockAlerts.filter((a) => a.severity === "high").length,
    medium: mockAlerts.filter((a) => a.severity === "medium").length,
    low: mockAlerts.filter((a) => a.severity === "low").length,
  },
  risk_trend: buildRiskTrend(),
  recent_alerts: mockAlerts.slice(0, 5),
};

function buildRiskTrend() {
  const rnd = seeded(42);
  const days: { date: string; critical: number; high: number; medium: number; low: number }[] = [];
  for (let i = 13; i >= 0; i -= 1) {
    const d = new Date(now - i * 24 * 60 * 60 * 1000);
    const date = `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    days.push({
      date,
      critical: Math.round(rnd() * 2),
      high: Math.round(1 + rnd() * 4),
      medium: Math.round(2 + rnd() * 5),
      low: Math.round(1 + rnd() * 4),
    });
  }
  return days;
}

// ---- 主机详情与遥测 ----

function genTelemetry(host: Host, points = 30, intervalMin = 2): TelemetryPoint[] {
  const rnd = seeded(Number(host.id.slice(0, 4)) || 7);
  const baseCpu = host.metrics?.cpu_percent ?? 20;
  const baseMem = host.metrics?.memory_percent ?? 40;
  const baseSent = host.metrics?.network_bytes_sent ?? 1_000_000;
  const baseRecv = host.metrics?.network_bytes_recv ?? 3_000_000;
  const out: TelemetryPoint[] = [];
  for (let i = points; i > 0; i -= 1) {
    const wave = Math.sin(i / 3) * 6;
    const cpu = Math.max(0, Math.min(99, baseCpu + wave + (rnd() - 0.5) * 10));
    const mem = Math.max(0, Math.min(99, baseMem + (rnd() - 0.5) * 6));
    out.push({
      collected_at: new Date(now - i * intervalMin * 60_000).toISOString(),
      cpu_percent: Number(cpu.toFixed(1)),
      memory_percent: Number(mem.toFixed(1)),
      network_bytes_sent: Math.round(baseSent * (0.9 + rnd() * 0.2)),
      network_bytes_recv: Math.round(baseRecv * (0.9 + rnd() * 0.2)),
    });
  }
  return out;
}

export const mockHostDetail = (host: Host): HostDetail => ({
  ...host,
  telemetry: genTelemetry(host),
  process_snapshot: [
    { pid: 1, name: "systemd", username: "root", started_at: iso(60 * 24 * 3) },
    { pid: 892, name: "mysqld", username: "mysql", started_at: iso(60 * 24 * 20) },
    { pid: 1204, name: "nginx", username: "www-data", started_at: iso(60 * 24 * 3) },
    { pid: 2310, name: "hostguard-agent", username: "root", started_at: iso(60) },
    { pid: 3422, name: "sshd", username: "root", started_at: iso(60 * 24 * 3) },
  ],
  listening_ports: [
    { protocol: "tcp", local_address: "0.0.0.0", local_port: 22, pid: 3422 },
    { protocol: "tcp", local_address: "127.0.0.1", local_port: 3306, pid: 892 },
    { protocol: "tcp", local_address: "0.0.0.0", local_port: 80, pid: 1204 },
    { protocol: "tcp", local_address: "0.0.0.0", local_port: 443, pid: 1204 },
  ],
  file_changes: [
    { path: "/etc/passwd", change_type: "modified", occurred_at: iso(60 * 26), sha256: "a".repeat(64), size: 1842 },
    { path: "/var/log/auth.log", change_type: "created", occurred_at: iso(90), sha256: "b".repeat(64), size: 409600 },
  ],
  security_events: [
    { event_type: "login_failure", severity: "high", occurred_at: iso(80), summary: "SSH 登录失败 12 次（root）", source_ip: "203.0.113.77", username: "root" },
    { event_type: "file_modified", severity: "critical", occurred_at: iso(60 * 26), summary: "敏感文件 /etc/passwd 被修改", source_ip: null, username: null },
    { event_type: "port_listening", severity: "low", occurred_at: iso(60 * 5), summary: "端口 443 开始监听（nginx）", source_ip: null, username: null },
  ],
  baseline_results: [
    { check_id: "cis-1.1", status: "pass", checked_at: iso(60 * 24), message: "文件系统挂载选项合规" },
    { check_id: "cis-5.4", status: "fail", checked_at: iso(60 * 24), message: "密码最短长度不足 12 位" },
    { check_id: "cis-3.6", status: "unavailable", checked_at: iso(60 * 24), message: "无 ip6tables 策略，未评估" },
  ],
});

// ---- 统一 mock 入口 ----

function paginate<T>(items: T[], params: URLSearchParams): Page<T> {
  const page = Math.max(1, Number(params.get("page") ?? 1));
  const pageSize = Math.max(1, Number(params.get("page_size") ?? 20));
  const start = (page - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    page,
    page_size: pageSize,
    total: items.length,
  };
}

export class MockNotFoundError extends Error {
  constructor(path: string) {
    super(`mock: no route for ${path}`);
    this.name = "MockNotFoundError";
  }
}

/** 模拟登录：admin/admin123 为管理员，其余任意账号按前缀分配角色 */
export async function mockLogin(username: string, password: string): Promise<{ token: string; user: CurrentUserLike }> {
  await delay(220);
  if (!username || !password) {
    throw new Error("请输入用户名和密码");
  }
  const role = username === "admin" ? "admin" : username === "analyst" ? "analyst" : "viewer";
  return {
    token: `mock-token-${username}`,
    user: { id: uuid(999), username, display_name: username === "admin" ? "安全管理员" : username, role },
  };
}

export interface MockContext {
  method: string;
  path: string;
  params: URLSearchParams;
  body?: unknown;
}

const UUID_RE = "[0-9a-f-]{36}";

function matcher(pattern: RegExp, path: string): RegExpMatchArray | null {
  return pattern.exec(path);
}

export async function handleMock(ctx: MockContext): Promise<unknown> {
  const { path, params, method, body } = ctx;
  await delay();

  switch (path) {
    case "/auth/csrf":
      return { token: `mock-csrf-${Date.now()}` };
    case "/auth/logout":
      return undefined;
    case "/auth/me":
      return { user: { id: uuid(999), username: "admin", display_name: "安全管理员", role: "admin" } };
    case "/dashboard/summary":
      return mockDashboard;
    case "/hosts":
      return paginate(mockHosts, params);
    case "/alerts":
      return paginate(mockAlerts, params);
    case "/rules":
      return mockRules;
    case "/reports":
      return paginate(mockReports, params);
    case "/notifications/channels":
      return mockChannels;
    case "/notifications/deliveries":
      return paginate(mockDeliveries, params);
    case "/users":
      return paginate(mockUsers, params);
    case "/audit":
      return paginate(mockAudit, params);
    default:
      break;
  }

  // /reports/{id}/download
  const reportDownload = matcher(new RegExp(`^/reports/(${UUID_RE})/download$`), path);
  if (reportDownload) {
    const report = mockReports.find((r) => r.id === reportDownload[1]);
    if (!report || report.status !== "completed") {
      throw new MockNotFoundError(path);
    }
    return new Blob([`HostGuard 报告：${report.title}\n这是一份由本地 mock 生成的演示报告。`], {
      type: "application/pdf",
    });
  }

  // /notifications/channels/{id}/test
  const channelTest = matcher(new RegExp(`^/notifications/channels/(${UUID_RE})/test$`), path);
  if (channelTest) {
    const channel = mockChannels.find((c) => c.id === channelTest[1]);
    if (!channel) throw new MockNotFoundError(path);
    const delivery: NotificationDelivery = {
      id: uuid(++mockSeq),
      channel_id: channel.id,
      channel_name: channel.name,
      status: "sent",
      subject: "【HostGuard】渠道测试消息",
      attempted_at: new Date().toISOString(),
      error: null,
    };
    mockDeliveries.unshift(delivery);
    return delivery;
  }

  // /notifications/channels/{id}
  const channelId = matcher(new RegExp(`^/notifications/channels/(${UUID_RE})$`), path);
  if (channelId) {
    const channel = mockChannels.find((c) => c.id === channelId[1]);
    if (!channel) throw new MockNotFoundError(path);
    if (method === "PATCH") {
      Object.assign(channel, body ?? {});
      return channel;
    }
    return channel;
  }

  // /notifications/channels (POST 新建)
  if (path === "/notifications/channels" && method === "POST") {
    const b = (body ?? {}) as Partial<NotificationChannel>;
    const channel: NotificationChannel = {
      id: uuid(++mockSeq),
      name: String(b.name ?? "未命名渠道"),
      type: (b.type as NotificationChannel["type"]) ?? "email",
      enabled: b.enabled ?? true,
      target: String(b.target ?? ""),
      created_at: new Date().toISOString(),
    };
    mockChannels.push(channel);
    return channel;
  }

  // /rules/{id} (PATCH)
  const ruleId = matcher(new RegExp(`^/rules/(${UUID_RE})$`), path);
  if (ruleId) {
    const rule = mockRules.find((r) => r.id === ruleId[1]);
    if (!rule) throw new MockNotFoundError(path);
    if (method === "PATCH") {
      Object.assign(rule, body ?? {});
      rule.updated_at = new Date().toISOString();
      return rule;
    }
    return rule;
  }

  // /rules (POST 新建)
  if (path === "/rules" && method === "POST") {
    const b = (body ?? {}) as Partial<DetectionRule>;
    const rule: DetectionRule = {
      id: uuid(++mockSeq),
      name: String(b.name ?? "未命名规则"),
      description: String(b.description ?? ""),
      severity: (b.severity as DetectionRule["severity"]) ?? "medium",
      enabled: b.enabled ?? true,
      kind: String(b.kind ?? "metric"),
      condition_field: String(b.condition_field ?? "cpu_percent"),
      condition_op: String(b.condition_op ?? ">="),
      window_seconds: Number(b.window_seconds ?? 300),
      threshold: Number(b.threshold ?? 1),
      updated_at: new Date().toISOString(),
    };
    mockRules.push(rule);
    return rule;
  }

  // /reports (POST 创建)
  if (path === "/reports" && method === "POST") {
    const b = (body ?? {}) as Partial<ReportJob>;
    const report: ReportJob = {
      id: uuid(++mockSeq),
      title: String(b.title ?? "安全报告"),
      status: "pending",
      scope: String(b.scope ?? "all_hosts"),
      report_type: String(b.report_type ?? "summary"),
      format: String(b.format ?? "pdf"),
      requested_by: "admin",
      requested_at: new Date().toISOString(),
      expires_at: null,
      error: null,
    };
    mockReports.unshift(report);
    return report;
  }

  // /alerts/{id}/transitions (POST)
  const alertTransition = matcher(new RegExp(`^/alerts/(${UUID_RE})/transitions$`), path);
  if (alertTransition && method === "POST") {
    const alert = mockAlerts.find((a) => a.id === alertTransition[1]);
    if (!alert) throw new MockNotFoundError(path);
    const b = (body ?? {}) as { to_status?: Alert["status"]; comment?: string };
    const toStatus = b.to_status ?? "resolved";
    const history = transitionsFor(alert);
    const transition: AlertTransition = {
      id: uuid(++mockSeq),
      from_status: alert.status,
      to_status: toStatus,
      comment: b.comment ?? null,
      actor: "admin",
      occurred_at: new Date().toISOString(),
    };
    alert.status = toStatus;
    alert.updated_at = transition.occurred_at;
    const detail: AlertDetail = { ...alert, transitions: [...history, transition] };
    return detail;
  }

  // /alerts/{id}
  const alertId = matcher(new RegExp(`^/alerts/(${UUID_RE})$`), path);
  if (alertId) {
    const alert = mockAlerts.find((a) => a.id === alertId[1]);
    if (!alert) throw new MockNotFoundError(path);
    const detail: AlertDetail = { ...alert, transitions: transitionsFor(alert) };
    return detail;
  }

  // /hosts/{id}
  const hostId = matcher(new RegExp(`^/hosts/(${UUID_RE})$`), path);
  if (hostId) {
    const host = mockHosts.find((h) => h.id === hostId[1]);
    if (!host) throw new MockNotFoundError(path);
    return mockHostDetail(host);
  }

  throw new MockNotFoundError(path);
}
