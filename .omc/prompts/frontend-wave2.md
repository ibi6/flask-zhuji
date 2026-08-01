# Frontend Wave 2 — 真实 API 接入 + 深度交互

wave1 已完成：登录/路由守卫/角色导航/11 页面/mock 适配器/Vitest 12 通过。
wave2 把 mock 换成真实 API，并补深度交互：

1. **真实 API 接入**：mock 分支默认关闭（USE_MOCKS=false），全部页面走真实 API；
   mock 层保留但仅作为显式开发开关。接通 hosts/alerts/rules/reports/notifications/
   users/audit/dashboard 全部端点，统一处理错误信封与分页信封。
2. **告警处置工作流**：告警列表支持批量/单个状态流转（open→investigating→resolved/ignored），
   调用 `/alerts/{id}/transitions`，详情展示状态历史。
3. **主机详情真实图表**：HostDetail 概览标签页用真实遥测数据渲染 CPU/内存/网络趋势图
   （轻量图表库或自绘 SVG 均可），进程/端口/事件/基线标签页接真实数据。
4. **规则管理**：admin 可创建/编辑/启停 DetectionRule（规则编辑器：名称/严重级别/条件字段/
   阈值/启用），analyst/viewer 只读。
5. **报告**：创建报告（范围/类型/格式），列表展示状态，completed 可下载。
6. **通知渠道**：admin 配置 webhook/email 渠道并测试发送，展示投递状态列表。
7. **仪表盘**：真实 KPI（在线主机/告警分布/风险趋势），保持浅色冷色 + 紫/靛点缀设计语言。

要求：Vitest 测试更新并全绿（mock 适配器供测试用）、tsc typecheck、vite build 通过；
mock 与真实数据绝不混用（mock 仅由 USE_MOCKS 显式开启）；**不要 git commit**（主代理统一处理提交）。
