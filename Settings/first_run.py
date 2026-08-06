from __future__ import annotations

from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent


# First-run helpers

# Merge manifest defaults with any existing settings.json keys.
def _build_initial_settings(existing: dict[str, Any], ui_port: int) -> dict[str, Any]:
    """Merge manifest defaults with any existing settings.json keys."""

    from Settings.settings import DEFAULTS

    initial: dict[str, Any] = dict(existing)
    for key, default in DEFAULTS.items():
        # ASLM passes --port on first_run; preserve an existing example-port if set.
        if key == "example-port":
            initial[key] = existing.get(key, ui_port)
        else:
            initial[key] = existing.get(key, default)
    return initial


# Print first-run output when --log is enabled.
def _print_summary(settings_file: Path, initial: dict[str, Any]) -> None:
    """Print first-run output when --log is enabled."""

    print(f"[ASLM-Example] Settings written to: {settings_file}")
    print(f"[ASLM-Example]   example-port   : {initial['example-port']}")
    print(f"[ASLM-Example]   example-select : {initial['example-select']}")
    print("[ASLM-Example] First-run setup complete.")
    print(
        "[ASLM-Example] Python packages (e.g. flask) are installed by ASLM into the "
        "host-managed module venv (see ASLM_ENGINE_ENV_DIR)."
    )


# Write settings.json on first install (pip install is handled by ASLM).
def run(log: bool = False, ui_port: int = 20100) -> None:
    """Write settings.json on first install (pip install is handled by ASLM)."""

    from Settings.settings import SETTINGS_FILE, load_settings, save_settings

    # Merge defaults without overwriting keys the user already has on disk.
    existing = load_settings()
    initial = _build_initial_settings(existing, ui_port=ui_port)
    save_settings(initial)

    if log:
        _print_summary(SETTINGS_FILE, initial)
