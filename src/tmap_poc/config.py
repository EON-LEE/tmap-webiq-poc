"""Shared configuration helpers.

Everything environment-specific (endpoints, subscription, agent names) is read from
the environment or a local `.env` file, never hardcoded. See config/runtime.example.env.
"""

import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    pass


def load_dotenv(path=None):
    """Minimal .env loader. Existing environment variables win."""
    p = pathlib.Path(path) if path else ROOT / ".env"
    if not p.exists():
        return False
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
    return True
