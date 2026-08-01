# Agent Wave 2 — FIM/事件/基线真实采集 + 策略执行

wave1 已完成：注册/签名 HTTP、SecretStore、SQLite 缓冲、psutil 采集器、调度器、CLI，45 测试通过。
wave1 的事件/FIM/基线适配器返回显式 unavailable——wave2 把它们做成真实现：

1. **FIM 文件完整性**：扫描配置的目录/文件集合，计算哈希与元数据快照，维护基线；
   检测变更（新增/修改/删除/权限变化）生成 FileChange 事件（含 before/after hash），
   支持增量扫描与忽略规则（.git 目录、临时文件等）。
2. **基线扫描**：生成 InventorySnapshot + BaselineResult，包含系统信息、已安装软件/服务清单、
   启动项、开放端口基线，与后续扫描 diff 出变化。
3. **事件采集适配器**：Windows Event Log（Security/System 频道）与 Linux（journald 或
   /var/log 关键文件）真实实现，映射到 SecurityEvent；无权限/不支持时返回显式 unavailable
   并记录原因（不允许 silent 吞掉）。
4. **策略执行**：从服务端 `/agent/policy` 拉取策略（采集间隔、开关、FIM 目录、事件频道），
   应用到调度器与采集器；策略拉取失败时保留上次策略并退避重试。
5. **采集器隔离**：FIM/事件/基线采集器失败不影响 metrics 主链路，健康日志如实记录。

要求：新增/更新 pytest 测试保持全绿（适配器用临时目录/模拟对象，不需要真 Event Log）；
匹配 telemetry.schema.json 与 conventions.md；**不要 git commit**（主代理统一处理提交）。
