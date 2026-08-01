# Backend Wave 2 — 遥测入库 + 告警引擎 + 报告/通知

wave1 已完成：认证/RBAC/agent 注册/签名 ingest 骨架、全部 API 骨架、81 测试通过。
wave2 把这些骨架变成真实功能：

1. **ingest 批次真实入库**：`/api/v1/agent/batches` 接收后，把 telemetry.schema.json 中的
   metrics/inventory/processes/listening_ports/events/file_changes/baseline_results
   解析并持久化到对应模型（MetricSample/InventorySnapshot/ProcessSnapshot/
   ListeningPortSnapshot/SecurityEvent/FileChange/BaselineResult）。批次仍保持幂等。
2. **规则评估引擎**：后台任务把新落库的遥测按 DetectionRule 条件匹配（如 CPU 均值阈值、
   新端口、新进程、高危事件），生成 Alert 并写入 AlertTransition，含去重与抑制策略。
3. **报告真实执行**：ReportJob 后台执行，聚合遥测数据生成报告内容（可下载，JSON/CSV），
   状态流转 pending→running→completed/failed。
4. **通知渠道投递**：NotificationChannel（webhook/email）真实发送骨架，NotificationDelivery
   状态 pending→retrying→sent/failed，含重试。
5. **主机在线状态**：根据 last_seen 心跳推断 online/degraded/offline（纳入 dashboard 与列表）。
6. **仪表盘真实聚合**：summary 返回真实统计（主机数/告警分布/近期事件/风险趋势），非骨架计数。

要求：新增/更新 pytest 测试保持全绿；遵循 contracts/conventions.md 与 telemetry.schema.json；
不内嵌密钥；**不要 git commit**（主代理统一处理提交）。
