from __future__ import annotations

from pathlib import Path

import pytest

from hostguard_agent.config import AgentConfig, load_config


def test_config_rejects_insecure_remote_server(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        AgentConfig(server_url="http://example.com", data_dir=tmp_path)


def test_loopback_http_is_allowed_for_local_development(tmp_path: Path) -> None:
    config = AgentConfig(server_url="http://127.0.0.1:5000/", data_dir=tmp_path)

    assert config.server_url == "http://127.0.0.1:5000"
    assert config.collection_interval_seconds == 10


def test_https_remote_host_is_allowed(tmp_path: Path) -> None:
    config = AgentConfig(server_url="https://hg.example/api", data_dir=tmp_path)
    assert config.server_url == "https://hg.example/api"


def test_http_remote_host_allowed_only_with_dev_flag(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        AgentConfig(server_url="http://10.0.0.5:8000", data_dir=tmp_path)
    config = AgentConfig(server_url="http://10.0.0.5:8000", data_dir=tmp_path, development=True)
    assert config.server_url == "http://10.0.0.5:8000"


def test_invalid_scheme_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="http or https"):
        AgentConfig(server_url="ftp://example.com", data_dir=tmp_path)


def test_localhost_hostname_is_treated_as_loopback(tmp_path: Path) -> None:
    config = AgentConfig(server_url="http://localhost:9000", data_dir=tmp_path)
    assert config.server_url == "http://localhost:9000"


def test_empty_server_url_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="server_url"):
        AgentConfig(server_url="", data_dir=tmp_path)


def test_invalid_intervals_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="collection_interval_seconds"):
        AgentConfig(
            server_url="https://hg.example",
            data_dir=tmp_path,
            collection_interval_seconds=0,
        )


def test_load_config_merges_file_env_and_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        'server_url = "https://from-file.example"\ncollection_interval_seconds = 42\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("HOSTGUARD_DATA_DIR", str(tmp_path))

    config = load_config(config_file, server_url="https://override.example")

    assert config.server_url == "https://override.example"  # explicit wins
    assert config.collection_interval_seconds == 42  # file value applies
    assert config.data_dir == tmp_path  # env value applies
