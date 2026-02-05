"""Configuration loading from file, environment, and CLI flags."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_BASE_URL = "https://rcsbusinessmessaging.googleapis.com"
DEFAULT_TIMEOUT = 30
DEFAULT_CONFIG_PATH = Path.home() / ".rcsclient.json"


class ConfigError(Exception):
    """Raised when configuration is invalid or incomplete."""
    pass


@dataclass
class Config:
    agent_id: str
    credentials_file: str
    base_url: str = DEFAULT_BASE_URL
    timeout: int = DEFAULT_TIMEOUT

    def validate(self) -> None:
        if not self.agent_id:
            raise ConfigError("agent_id is required (--agent-id or RCS_AGENT_ID)")
        if not self.credentials_file:
            raise ConfigError(
                "credentials file is required (--credentials or RCS_CREDENTIALS)"
            )
        path = Path(self.credentials_file)
        if not path.exists():
            raise ConfigError(f"credentials file not found: {self.credentials_file}")


def _load_file(path: Path) -> dict:
    """Load config from a JSON file, returning empty dict if missing."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ConfigError(f"failed to read config file {path}: {e}")


def load_config(
    cli_agent_id: Optional[str] = None,
    cli_credentials: Optional[str] = None,
    cli_base_url: Optional[str] = None,
    cli_timeout: Optional[int] = None,
    cli_config_path: Optional[str] = None,
) -> Config:
    """Load configuration with precedence: CLI flags > env vars > config file."""

    config_path = Path(cli_config_path) if cli_config_path else DEFAULT_CONFIG_PATH
    file_cfg = _load_file(config_path)

    agent_id = (
        cli_agent_id
        or os.environ.get("RCS_AGENT_ID")
        or file_cfg.get("agent_id", "")
    )
    credentials_file = (
        cli_credentials
        or os.environ.get("RCS_CREDENTIALS")
        or file_cfg.get("credentials_file", "")
    )
    base_url = (
        cli_base_url
        or os.environ.get("RCS_BASE_URL")
        or file_cfg.get("base_url", DEFAULT_BASE_URL)
    )
    timeout_str = os.environ.get("RCS_TIMEOUT")
    timeout = (
        cli_timeout
        if cli_timeout is not None
        else int(timeout_str) if timeout_str else file_cfg.get("timeout", DEFAULT_TIMEOUT)
    )

    return Config(
        agent_id=agent_id,
        credentials_file=credentials_file,
        base_url=base_url,
        timeout=timeout,
    )
