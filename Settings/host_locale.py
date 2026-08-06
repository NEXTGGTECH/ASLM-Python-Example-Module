from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
HOST_LOCALE_FILE = BASE_DIR / "Settings" / "host_locale.json"


# File I/O

# Write JSON atomically via a temporary file.
def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically via a temporary file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


# Persist the host locale JSON from apply_aslm_locale --file.
def save_host_locale_payload(data: dict[str, Any]) -> None:
    """Persist the host locale JSON from apply_aslm_locale --file."""

    if not isinstance(data, dict):
        raise TypeError("host locale payload must be a dict")
    _atomic_write_json(HOST_LOCALE_FILE, data)


# Return Settings/host_locale.json or None if missing or invalid.
def load_host_locale() -> dict[str, Any] | None:
    """Return Settings/host_locale.json or None if missing or invalid."""

    if not HOST_LOCALE_FILE.exists():
        return None
    try:
        raw = HOST_LOCALE_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not read host locale file %s: %s", HOST_LOCALE_FILE, exc)
        return None
    raw = raw.lstrip("\ufeff").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Could not parse host locale file %s: %s", HOST_LOCALE_FILE, exc)
        return None
    return parsed if isinstance(parsed, dict) else None


# Return the BCP-47 language code from the snapshot.
def get_language() -> str:
    """Return the BCP-47 language code from the snapshot."""

    payload = load_host_locale()
    if payload:
        return str(payload.get("language", "en"))
    return "en"
