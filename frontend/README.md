# HostGuard 前端演示

基于 React 19 + Vite 的主机安全态势感知平台前端。在线演示使用 **Mock 数据**，无需后端即可体验完整 UI。

## 在线预览

推送 `codex/hostguard-frontend` 分支并启用 GitHub Pages 后，访问：

**https://ibi6.github.io/flask-zhuji/**

登录页提供三角色一键登录：

| 角色 | 账号 | 说明 |
|------|------|------|
| 管理员 | `admin` | 用户管理、通知配置 |
| 分析员 | `analyst` | 威胁情报、AI 分析、报告 |
| 只读 | `viewer` | 总览、主机、告警、审计 |

Mock 模式下任意密码均可登录。

## 本地开发

```bash
npm ci
$env:VITE_USE_MOCK="true"   # PowerShell
npm run dev
```

浏览器打开 http://127.0.0.1:5180

## 部署到 GitHub Pages

1. 推送本分支到 `origin`
2. 仓库 **Settings → Pages → Build and deployment** 选择 **GitHub Actions**
3. 等待 `Deploy GitHub Pages` 工作流完成

工作流会自动跑测试、以 Mock 模式构建静态站点并发布。

## 脚本

| 命令 | 说明 |
|------|------|
| `npm run dev` | 本地开发 |
| `npm test` | 单元测试 |
| `npm run build:pages` | GitHub Pages 构建（含 SPA 404 回退） |
