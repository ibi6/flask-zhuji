# Frontend wave 1 task

Work only in `C:\Users\33185\Desktop\毕业设计\fan\.omc\worktrees\hostguard\frontend` on branch `codex/hostguard-frontend`.
Do not edit root contracts or files outside `frontend/**`.

Build the production-ready React frontend foundation for HostGuard:

- React 19 + Vite + TypeScript + TailwindCSS + lucide-react + React Router + TanStack Query. Use a lightweight chart library only where it materially improves real charts.
- Implement API client with same-origin credentials, CSRF handling, structured errors and typed models matching `contracts/conventions.md`.
- Authentication store/context, `/login`, protected routes, role-aware navigation for admin/analyst/viewer and unauthorized/error handling.
- Full responsive dashboard shell with collapsible sidebar and top bar. Product name HostGuard and subtitle 主机安全态势感知平台.
- Pages/routes: overview, hosts, host detail tabs, alerts, rules, reports, notifications, users, audit. For wave 1 implement polished real layouts using a local mock adapter behind an explicit development flag while keeping API integration interfaces ready. Never disguise mock/simulated data as real.
- Visual direction: light cool canvas, restrained violet/indigo accent, semantic green/amber/red risk states, soft shadows, large rounded surfaces per user design preference, dense operational information, no marketing landing page or nested cards.
- Implement loading, empty, error, disabled, focus, hover and mobile states. Use icons with accessible labels/tooltips.
- Add Vitest/Testing Library tests for login, route guards, role navigation, API error handling and representative page states. Configure lint, typecheck and production build.

Run npm tests, typecheck and build. Commit all changes to your branch. Report commit SHA, commands and failures to the parent. Do not spawn subagents.
