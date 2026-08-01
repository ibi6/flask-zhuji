# Agent wave 1 task

Work only in `C:\Users\33185\Desktop\毕业设计\fan\.omc\worktrees\hostguard\agent` on branch `codex/hostguard-agent`.
Do not edit root contracts or files outside `agent/**`.

Build the production-quality HostGuard Python agent foundation:

- Create an installable Python 3.11 package and CLI `hostguard-agent` under `agent/`, with configuration from file/environment and no embedded secrets.
- Implement enrollment client and signed HTTP client matching `contracts/conventions.md` and `contracts/telemetry.schema.json`.
- SecretStore abstraction: Windows DPAPI via safe standard APIs, Linux file storage with `0600`, and a test-only memory store.
- Local SQLite spool with idempotent batch UUIDs, bounded 256 MB / 7 day retention, FIFO retry, exponential backoff and corruption/error handling.
- Cross-platform collectors using psutil: inventory, CPU/memory/disk/network, process summaries without full command lines or environment variables, listening ports, UTC timestamps.
- Scheduler/orchestrator with metrics every 10s, process/ports every 60s, inventory every 10m, policy refresh, graceful shutdown, collector isolation, and health logging.
- Prepare collector interfaces for Windows/Linux event, baseline and FIM adapters without TODO stubs: unsupported/permission cases must return explicit unavailable results.
- CLI commands: enroll, run, status, collect-once. Validate server URL and require HTTPS except localhost unless explicit development override.
- Add pytest tests for signing, secret stores, spool retry/limits, collectors, payload schema compatibility, URL validation and orchestration failure isolation.

Run tests and lint/type checks that are feasible. Commit all changes to your branch. Report commit SHA, commands and failures to the parent. Do not spawn subagents.

