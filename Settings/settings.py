from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_FILE = BASE_DIR / "Settings" / "settings.json"

# Keys withheld from GET /api/settings (password fields show *** when set).
SECRET_KEYS: frozenset[str] = frozenset({"example-password"})

# Env keys listed for documentation only; not persisted in settings.json.
IGNORED_ENV_KEYS: frozenset[str] = frozenset({
    "ASLM_MODULE_ID",
    "ASLM_MODULE_DIR",
    "ASLM_MODULE_INTEROP_BASE_URL",
    "ASLM_MODULE_INTEROP_PORT",
})

# Default setting values (must match ASLM_Module.json defaults).
DEFAULTS: dict[str, Any] = {
    "example-port": 20100,
    "example-string": "Example Python Module - ASLM reference UI",
    "example-bool": True,
    "example-int": 10000,
    "example-number": 0.25,
    "example-password": "sk-1234-5678-9012-3456-7890",
    "example-select": "debug",
    "python-runtime": True,
    "python-runtime_path": None,
    "python-runtime_data": None,
    "python-runtime_models": None,
}

# In-memory settings cache
_settings_lock = threading.RLock()
_settings_cache: dict[str, Any] | None = None


# Load settings.json merged with DEFAULTS.
def load_settings() -> dict[str, Any]:
    """Load settings.json merged with DEFAULTS."""

    global _settings_cache
    with _settings_lock:
        if _settings_cache is not None:
            return dict(_settings_cache)

        # Read disk once, then overlay DEFAULTS for missing keys.
        persisted: dict[str, Any] = {}
        if SETTINGS_FILE.exists():
            try:
                raw = SETTINGS_FILE.read_text(encoding="utf-8")
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    persisted = loaded
            except Exception:
                pass

        merged = dict(DEFAULTS)
        merged.update(persisted)
        _settings_cache = merged
        return dict(_settings_cache)


# Persist settings.json using a replace-on-success write.
def save_settings(data: dict[str, Any]) -> None:
    """Persist settings.json using a replace-on-success write."""

    global _settings_cache
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace avoids half-written settings.json on crash.
    tmp = SETTINGS_FILE.with_suffix(".json.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.write("\n")
        os.replace(tmp, SETTINGS_FILE)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise

    with _settings_lock:
        _settings_cache = dict(data)


# Return one setting value for get_setting.
def get(key: str) -> Any:
    """Return one setting value for get_setting."""

    settings = load_settings()
    return settings.get(key, DEFAULTS.get(key))


# Persist one setting value for set_setting.
def set(key: str, value: Any) -> None:
    """Persist one setting value for set_setting."""

    with _settings_lock:
        settings = load_settings()
        settings[key] = value
        save_settings(settings)


# Coerce an ASLM {value} string into a Python scalar or JSON value.
def normalize_setting_value(raw: str) -> Any:
    """Coerce an ASLM {value} string into a Python scalar or JSON value."""

    if raw is None:
        return None

    stripped = raw.strip()

    # Boolean literals from ASLM setExec.
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False

    if stripped == "null":
        return None

    # Integer before float so "42" stays int.
    try:
        return int(stripped)
    except ValueError:
        pass

    try:
        return float(stripped)
    except ValueError:
        pass

    # Fallback: try with comma as decimal separator (e.g. "0,25" → 0.25).
    if "," in stripped:
        try:
            return float(stripped.replace(",", "."))
        except ValueError:
            pass

    # JSON object/array when the host sends structured values.
    if stripped.startswith(("{", "[")):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    return raw


# Return settings for the dashboard API with secrets redacted.
def get_public_settings() -> dict[str, Any]:
    """Return settings for the dashboard API with secrets redacted."""

    settings = load_settings()
    public: dict[str, Any] = {}
    for key, value in settings.items():
        public[key] = "***" if key in SECRET_KEYS and value else value
    return public


# Return all ASLM_* variables injected by the host.
def collect_aslm_environment() -> dict[str, str]:
    """Return all ASLM_* variables injected by the host."""

    return {
        key: value
        for key, value in os.environ.items()
        if key.startswith("ASLM_")
    }
