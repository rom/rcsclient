"""Tests for configuration loading."""

import json
import os
import tempfile

import pytest

from rcsclient.config import load_config, Config, ConfigError


def test_config_from_cli_flags():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        f.write("{}")
        creds_path = f.name

    try:
        config = load_config(
            cli_agent_id="test-agent",
            cli_credentials=creds_path,
            cli_base_url="https://custom.api.com",
            cli_timeout=60,
        )
        assert config.agent_id == "test-agent"
        assert config.credentials_file == creds_path
        assert config.base_url == "https://custom.api.com"
        assert config.timeout == 60
    finally:
        os.unlink(creds_path)


def test_config_from_env(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        f.write("{}")
        creds_path = f.name

    try:
        monkeypatch.setenv("RCS_AGENT_ID", "env-agent")
        monkeypatch.setenv("RCS_CREDENTIALS", creds_path)
        monkeypatch.setenv("RCS_TIMEOUT", "45")

        config = load_config()
        assert config.agent_id == "env-agent"
        assert config.credentials_file == creds_path
        assert config.timeout == 45
    finally:
        os.unlink(creds_path)


def test_config_from_file():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as creds:
        creds.write("{}")
        creds_path = creds.name

    cfg = {
        "agent_id": "file-agent",
        "credentials_file": creds_path,
        "timeout": 15,
    }
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(cfg, f)
        config_path = f.name

    try:
        config = load_config(cli_config_path=config_path)
        assert config.agent_id == "file-agent"
        assert config.credentials_file == creds_path
        assert config.timeout == 15
    finally:
        os.unlink(creds_path)
        os.unlink(config_path)


def test_cli_overrides_env(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        f.write("{}")
        creds_path = f.name

    try:
        monkeypatch.setenv("RCS_AGENT_ID", "env-agent")
        config = load_config(cli_agent_id="cli-agent", cli_credentials=creds_path)
        assert config.agent_id == "cli-agent"
    finally:
        os.unlink(creds_path)


def test_validate_missing_agent_id():
    config = Config(agent_id="", credentials_file="/some/path")
    with pytest.raises(ConfigError, match="agent_id is required"):
        config.validate()


def test_validate_missing_credentials():
    config = Config(agent_id="test", credentials_file="")
    with pytest.raises(ConfigError, match="credentials file is required"):
        config.validate()


def test_validate_nonexistent_credentials():
    config = Config(agent_id="test", credentials_file="/nonexistent/path.json")
    with pytest.raises(ConfigError, match="credentials file not found"):
        config.validate()
