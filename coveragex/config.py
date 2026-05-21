"""Configuration & environment loading.

Loads secrets from gitignored config/.env (no python-dotenv dependency),
resolves project paths, and reads the versioned JSON configs.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FINAL_DIR = DATA_DIR / "final"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
LOGS_DIR = PROJECT_ROOT / "logs"

DB_PATH = DATA_DIR / "vehicle_signal_graph.sqlite"

# Reference year for age math. Overridable via env for deterministic tests.
REFERENCE_YEAR = int(os.environ.get("COVERAGEX_REFERENCE_YEAR", datetime.now().year))


def _parse_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE .env parser. Ignores comments/blank lines."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


@lru_cache(maxsize=1)
def _env() -> dict[str, str]:
    """Merge real OS env over config/.env (OS env wins)."""
    merged = _parse_env_file(CONFIG_DIR / ".env")
    merged.update({k: v for k, v in os.environ.items()})
    return merged


def get_env(key: str, default: str | None = None) -> str | None:
    return _env().get(key, default)


def require_env(key: str) -> str:
    val = get_env(key)
    if not val:
        raise RuntimeError(
            f"Missing required env var '{key}'. Set it in config/.env "
            f"(see config/.env.example). Secrets are never committed."
        )
    return val


def nhtsa_base() -> str:
    return get_env("NHTSA_API_BASE", "https://vpic.nhtsa.dot.gov/api") or (
        "https://vpic.nhtsa.dot.gov/api"
    )


@lru_cache(maxsize=2)
def _load_json(name: str) -> dict:
    path = CONFIG_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    return json.loads(path.read_text())


def scoring_config() -> dict:
    return _load_json("scoring_config.json")


def source_config() -> dict:
    return _load_json("source_config.json")


def ensure_dirs() -> None:
    for d in (RAW_DIR, PROCESSED_DIR, FINAL_DIR, OUTPUTS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
