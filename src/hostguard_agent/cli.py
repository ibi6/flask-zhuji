"""Command line interface for the HostGuard agent.

Commands:

* ``enroll`` -- exchange a one-time token for agent credentials and store them.
* ``run`` -- start the scheduled collection/shipping loop.
* ``status`` -- report enrollment, buffer and adapter status.
* ``collect-once`` -- collect a full telemetry batch and print it as JSON.

Server URLs are validated by :class:`AgentConfig`: HTTPS is required for
remote hosts unless ``--dev`` is passed.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .adapters import default_baseline_provider, default_event_source, default_fim_provider
from .buffer import SQLiteBatchBuffer
from .collector import SystemCollector
from .config import AgentConfig, load_config
from .credentials import CredentialStore, LinuxFileCredentialStore, WindowsDpapiCredentialStore
from .enroll import EnrollmentError, enroll
from .http_client import SignedHTTPClient
from .orchestrator import Orchestrator

logger = logging.getLogger(__name__)

__all__ = ["main"]


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=None, help="TOML or JSON config file")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="allow plain HTTP for local development (HTTPS required otherwise)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hostguard-agent",
        description="HostGuard host telemetry agent",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    enroll_parser = subparsers.add_parser("enroll", help="enroll this host and store credentials")
    enroll_parser.add_argument("--server", required=True, help="backend server URL")
    enroll_parser.add_argument(
        "--token", default=None, help="one-time enrollment token (or HOSTGUARD_ENROLL_TOKEN)"
    )
    enroll_parser.add_argument("--data-dir", type=Path, default=None, help="agent data directory")
    _add_common_flags(enroll_parser)

    run_parser = subparsers.add_parser("run", help="run the collection loop until interrupted")
    run_parser.add_argument("--data-dir", type=Path, default=None, help="agent data directory")
    run_parser.add_argument("--log-level", default="INFO", help="logging level (default INFO)")
    _add_common_flags(run_parser)

    status_parser = subparsers.add_parser("status", help="report enrollment and buffer status")
    status_parser.add_argument("--data-dir", type=Path, default=None, help="agent data directory")
    _add_common_flags(status_parser)

    collect_parser = subparsers.add_parser(
        "collect-once", help="collect one telemetry batch and print it"
    )
    collect_parser.add_argument("--data-dir", type=Path, default=None, help="agent data directory")
    _add_common_flags(collect_parser)

    return parser


def _config_from_args(args: argparse.Namespace) -> AgentConfig:
    return load_config(
        args.config,
        server_url=getattr(args, "server", None),
        data_dir=getattr(args, "data_dir", None),
        development=args.dev or None,
    )


def _credential_store(data_dir: Path) -> CredentialStore:
    path = data_dir / "credentials.json"
    if os.name == "nt":
        return WindowsDpapiCredentialStore(path)
    return LinuxFileCredentialStore(path)


def cmd_enroll(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    token = args.token or config.enroll_token
    if not token:
        print(
            "error: enrollment token required (--token or HOSTGUARD_ENROLL_TOKEN)",
            file=sys.stderr,
        )
        return 2
    config.ensure_dirs()
    try:
        credentials = enroll(
            config.server_url,
            token,
            timeout=config.http_timeout_seconds,
            verify=config.http_verify,
        )
    except EnrollmentError as exc:
        print(f"error: enrollment failed: {exc}", file=sys.stderr)
        return 1
    store = _credential_store(config.data_dir)
    store.save(credentials)
    print(f"enrolled agent {credentials.agent_id}")
    print(f"credentials stored at {config.data_dir / 'credentials.json'}")
    print("the agent secret is never displayed again; delete this host from the")
    print("backend to revoke it")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = _config_from_args(args)
    config.ensure_dirs()
    try:
        credentials = _credential_store(config.data_dir).load()
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: not enrolled ({exc}); run 'hostguard-agent enroll' first", file=sys.stderr)
        return 1

    collector = SystemCollector()
    buffer = SQLiteBatchBuffer(
        config.data_dir / "queue.db",
        max_payload_bytes=config.max_payload_bytes,
        retention_days=config.retention_days,
        base_backoff_seconds=config.base_backoff_seconds,
        max_backoff_seconds=config.max_backoff_seconds,
    )
    client = SignedHTTPClient(
        base_url=config.server_url,
        agent_id=credentials.agent_id,
        secret=credentials.secret,
        timeout=config.http_timeout_seconds,
        verify=config.http_verify,
    )
    orchestrator = Orchestrator(
        config=config,
        collector=collector,
        buffer=buffer,
        client=client,
        event_source=default_event_source(),
        baseline_provider=default_baseline_provider(),
        fim_provider=default_fim_provider(config.data_dir, config.fim_watch_dirs),
    )
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: orchestrator.stop())
    logger.info("hostguard-agent %s starting (server=%s)", __version__, config.server_url)
    orchestrator.run()
    logger.info("hostguard-agent stopped gracefully")
    return 0


def _effective_data_dir(args: argparse.Namespace) -> Path:
    """Resolve the data directory without requiring a valid server URL."""
    if args.data_dir is not None:
        return Path(args.data_dir)
    if args.config is not None:
        try:
            raw = AgentConfig.from_file(args.config)
            if "data_dir" in raw:
                return Path(raw["data_dir"])
        except ValueError:
            pass
    env_dir = os.environ.get("HOSTGUARD_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".hostguard"


def cmd_status(args: argparse.Namespace) -> int:
    data_dir = _effective_data_dir(args)
    try:
        config = _config_from_args(args)
    except ValueError as exc:
        print(f"server:      unset ({exc})")
        config = None
    if config is not None:
        print(f"server:      {config.server_url}")
    print(f"data dir:    {data_dir}")
    store = _credential_store(data_dir)
    try:
        credentials = store.load()
    except (FileNotFoundError, ValueError) as exc:
        print(f"enrolled:    no ({exc})")
        return 0
    print(f"enrolled:    yes (agent {credentials.agent_id})")
    buffer = SQLiteBatchBuffer(data_dir / "queue.db")
    try:
        stats = buffer.stats()
        print(
            f"pending:     {stats.pending_count} batches "
            f"({stats.payload_bytes} bytes, {stats.retrying_count} retrying)"
        )
    finally:
        buffer.close()
    policy = data_dir / "policy.json"
    if policy.exists():
        print("policy:      cached locally")
    return 0


def cmd_collect_once(args: argparse.Namespace) -> int:
    # Validate the configured server URL if one is present; local collection
    # does not require a backend.
    try:
        _config_from_args(args)
    except ValueError as exc:
        logger.warning("server not configured; collecting locally (%s)", exc)
    collector = SystemCollector()
    batch = collector.collect(include_details=True, inventory=True)
    print(json.dumps(batch, indent=2, ensure_ascii=True))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {
        "enroll": cmd_enroll,
        "run": cmd_run,
        "status": cmd_status,
        "collect-once": cmd_collect_once,
    }
    try:
        return commands[args.command](args)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
