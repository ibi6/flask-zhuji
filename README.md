# HostGuard · 主机安全态势感知平台

基于 Flask + React 的毕业设计项目：**主机安全态势感知系统**（HostGuard）。包含 Agent 采集、后端 API、SOC 前端仪表盘。

## 在线演示

前端已部署 GitHub Pages，**Mock 模式**，无需后端即可体验完整 UI：

**https://ibi6.github.io/flask-zhuji/**

登录页点击三角色卡片一键登录：

| 角色 | 账号 | 权限概要 |
|------|------|----------|
| 管理员 | admin | 用户管理、通知配置 |
| 分析员 | analyst | 威胁情报、AI 分析、报告 |
| 只读 | viewer | 总览、主机、告警、审计 |

Mock 模式下任意密码均可登录。

## 仓库分支

| 分支 | 内容 |
|------|------|
| [codex/hostguard-frontend](https://github.com/ibi6/flask-zhuji/tree/codex/hostguard-frontend) | React 19 前端 + GitHub Pages 部署 |
| [codex/hostguard-backend](https://github.com/ibi6/flask-zhuji/tree/codex/hostguard-backend) | Flask 3 后端 API |
| [codex/hostguard-agent](https://github.com/ibi6/flask-zhuji/tree/codex/hostguard-agent) | 主机 Agent（Python） |
| [codex/hostguard-system](https://github.com/ibi6/flask-zhuji/tree/codex/hostguard-system) | 系统整合 / 契约 |

## 本地开发（前端）

```bash
cd frontend
npm ci
npm run dev
```

PowerShell 下启用 Mock：

```powershell
$env:VITE_USE_MOCK = "true"
npm run dev
```

浏览器打开 http://127.0.0.1:5180

## 本地开发（Agent）

```bash
cd agent
uv sync
uv run pytest
uv run hostguard-agent --help
```

## 契约与 API

- `contracts/openapi.yaml` — REST API 定义
- `contracts/conventions.md` — 错误信封、分页等约定
- `contracts/telemetry.schema.json` — Agent 遥测 schema

## 技术栈

- **前端**：React 19、Vite、TanStack Query、TailwindCSS
- **后端**：Flask 3
- **Agent**：Python 3.11+、httpx

---

毕业设计 · 基于 Flask 的主机安全态势感知系统
