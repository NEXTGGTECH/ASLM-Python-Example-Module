from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

# Prepare project imports
_BASE_DIR = Path(__file__).resolve().parent.parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))


# Create and configure the Flask application.
def create_app() -> Flask:
    """Create and configure the Flask application."""

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )

    # Page
    @app.get("/")
    # Render the reference dashboard.
    def index():
        """Render the reference dashboard."""

        from Settings.host_theme import get_effective_theme, load_host_theme
        from Settings.host_locale import load_host_locale

        # Embed snapshots for inline theme script and optional client-side use.
        theme_payload = load_host_theme() or {}
        locale_payload = load_host_locale() or {}
        effective_theme = get_effective_theme()

        module_version = ""
        try:
            manifest = json.loads((_BASE_DIR / "ASLM_Module.json").read_text(encoding="utf-8"))
            module_version = manifest.get("version", "")
        except Exception:
            pass

        return render_template(
            "index.html",
            theme=effective_theme,
            theme_payload=json.dumps(theme_payload),
            locale_payload=json.dumps(locale_payload),
            version=module_version,
        )

    # API info
    @app.get("/api/info")
    # Return ASLM env vars, manifest summary, and runtime paths.
    def api_info():
        """Return ASLM env vars, manifest summary, and runtime paths."""

        from Settings.settings import collect_aslm_environment

        aslm_env = collect_aslm_environment()

        manifest_summary = _manifest_summary()

        return jsonify({
            "moduleId": os.environ.get("ASLM_MODULE_ID", "(not set — not launched by ASLM)"),
            "moduleDir": os.environ.get("ASLM_MODULE_DIR", str(_BASE_DIR)),
            "uiPort": os.environ.get("ASLM_UI_PORT", "(not set)"),
            "engineEnvDir": os.environ.get("ASLM_ENGINE_ENV_DIR", "(not set)"),
            "pythonExecutable": sys.executable,
            "interopBaseUrl": os.environ.get("ASLM_MODULE_INTEROP_BASE_URL", "(not set)"),
            "interopPort": os.environ.get("ASLM_MODULE_INTEROP_PORT", "(not set)"),
            "allAslmEnvVars": aslm_env,
            "manifest": manifest_summary,
        })

    # API settings
    @app.get("/api/settings")
    # Return settings.json values enriched with manifest metadata.
    def api_settings():
        """Return settings.json values enriched with manifest metadata."""

        from Settings.settings import get_public_settings

        settings = get_public_settings()

        # Build a lookup table from manifest setting definitions.
        manifest_path = _BASE_DIR / "ASLM_Module.json"
        setting_meta: dict[str, dict[str, Any]] = {}
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for s in manifest.get("settings", []):
                key = s.get("key", "")
                setting_meta[key] = {
                    "type": s.get("type", "string"),
                    "name": s.get("name", key),
                    "description": s.get("description", ""),
                    "allowedValues": s.get("allowedValues"),
                    "default": s.get("default"),
                }
        except Exception:
            pass

        # Join runtime values with type, labels, and allowedValues for the UI table.
        enriched = []
        for key, value in settings.items():
            meta = setting_meta.get(key, {})
            enriched.append({
                "key": key,
                "value": value,
                "type": meta.get("type", "string"),
                "name": meta.get("name", key),
                "description": meta.get("description", ""),
                "allowedValues": meta.get("allowedValues"),
                "default": meta.get("default"),
            })

        return jsonify({"settings": enriched})

    # API theme
    @app.get("/api/theme")
    # Return Settings/host_theme.json (canonical colors.* tokens).
    def api_theme():
        """Return Settings/host_theme.json (canonical colors.* tokens)."""

        from Settings.host_theme import get_effective_theme, load_host_theme

        payload = load_host_theme()
        if payload is None:
            return jsonify({
                "available": False,
                "message": "No theme snapshot yet — ASLM has not pushed a theme to this module.",
                "theme": "dark",
                "appearance": "Dark",
                "colors": {},
            })

        return jsonify({
            "available": True,
            "theme": get_effective_theme(),
            "snapshotPath": str(_BASE_DIR / "Settings" / "host_theme.json"),
            "rawPayload": payload,
            **payload,
        })

    # API locale
    @app.get("/api/locale")
    # Return Settings/host_locale.json (language, displayName).
    def api_locale():
        """Return Settings/host_locale.json (language, displayName)."""

        from Settings.host_locale import get_language, load_host_locale

        payload = load_host_locale()
        if payload is None:
            return jsonify({
                "available": False,
                "message": "No locale snapshot yet — ASLM has not pushed a locale to this module.",
                "language": "en",
                "displayName": "English",
            })

        return jsonify({
            "available": True,
            "language": get_language(),
            "snapshotPath": str(_BASE_DIR / "Settings" / "host_locale.json"),
            "rawPayload": payload,
            **payload,
        })

    # API downloads
    @app.get("/api/downloads")
    # Run all five bridge operations in-process for the dashboard.
    def api_downloads():
        """Run all five bridge operations in-process for the dashboard."""

        from Services.downloads_bridge import dispatch

        # Exercise every bridge operation in-process (no subprocess).
        demo_calls: list[tuple[str, dict[str, Any]]] = [
            ("list_categories", {}),
            ("list_items", {"categoryId": "example-catalog"}),
            (
                "describe_item",
                {
                    "categoryId": "example-catalog",
                    "resourceKey": "example:hello-world",
                },
            ),
            (
                "resolve_install",
                {
                    "categoryId": "example-catalog",
                    "resourceKey": "example:hello-world:latest",
                },
            ),
            (
                "resolve_uninstall",
                {
                    "categoryId": "example-catalog",
                    "resourceKey": "example:hello-world:latest",
                },
            ),
        ]

        operations = []
        for operation, params in demo_calls:
            request_body = {"operation": operation, **params}
            operations.append({
                "operation": operation,
                "request": request_body,
                "response": dispatch(request_body),
            })

        # Attach manifest excerpts so the UI can show categories/targets.
        manifest = _manifest_summary()
        bridge_manifest = manifest.get("downloadsBridge") or {}

        return jsonify({
            "protocolVersion": bridge_manifest.get("protocolVersion", 1),
            "entryPoint": bridge_manifest.get("entryPoint", "main.py downloads_bridge"),
            "protocolNote": (
                "Protocol v1: one JSON object on stdin (fields: operation, categoryId?, resourceKey?), "
                "one JSON envelope on stdout (protocolVersion, success, categories|items|itemDetail|installManifest|…). "
                "Production entry point: main.py downloads_bridge. "
                "Target example_data resolves to module Data/example-downloads/."
            ),
            "operations": operations,
            "manifestCategories": bridge_manifest.get("categories", []),
            "manifestTargets": bridge_manifest.get("targets", {}),
        })

    # API interop
    @app.get("/api/interop")
    # Proxy GET /v1/registry and include host HTTP exchange metadata.
    def api_interop():
        """Proxy GET /v1/registry and include host HTTP exchange metadata."""

        from Services.aslm_interop_client import get_registry_exchange, is_available

        if not is_available():
            return jsonify({
                "available": False,
                "message": (
                    "ASLM_MODULE_INTEROP_BASE_URL is not set. "
                    "This endpoint only works when the module is launched by ASLM "
                    "with moduleInterop.client.enabled: true."
                ),
            })

        try:
            # Proxy to ASLM loopback; include raw HTTP exchange for the log panel.
            registry, host_exchange = get_registry_exchange()
            caller_id = os.environ.get("ASLM_MODULE_ID", "aslm-python-example")
            return jsonify({
                "available": True,
                "callerModuleId": caller_id,
                "hostExchange": host_exchange,
                **registry,
            })
        except Exception as exc:
            return jsonify({"available": False, "error": str(exc)}), 502

    @app.get("/api/interop/spec")
    # Return INTEROP_API_SPEC for the Supported HTTP API table.
    def api_interop_spec():
        """Return INTEROP_API_SPEC for the Supported HTTP API table."""

        from Services.aslm_interop_client import INTEROP_API_SPEC, is_available

        base_url = os.environ.get("ASLM_MODULE_INTEROP_BASE_URL", "").strip() or None
        return jsonify({
            "available": is_available(),
            "interopBaseUrl": base_url,
            **INTEROP_API_SPEC,
        })

    # API interop start
    @app.post("/api/interop/start")
    # Proxy POST /v1/modules/start for the dashboard Start actions.
    def api_interop_start():
        """Proxy POST /v1/modules/start for the dashboard Start actions."""

        from Services.aslm_interop_client import is_available, request_start_exchange

        if not is_available():
            return jsonify({
                "available": False,
                "message": "ASLM_MODULE_INTEROP_BASE_URL is not set.",
            }), 503

        body = request.get_json(silent=True) or {}
        module_ids: list[str] = body.get("moduleIds", [])
        if not module_ids:
            return jsonify({"error": "moduleIds array is required"}), 400

        caller_id = os.environ.get("ASLM_MODULE_ID", "aslm-python-example")

        try:
            # Forward to POST /v1/modules/start on the host interop server.
            result, host_exchange = request_start_exchange(
                caller_module_id=caller_id,
                module_ids=module_ids,
            )
            return jsonify({
                "available": True,
                "callerModuleId": caller_id,
                "hostExchange": host_exchange,
                "proxyRequest": {
                    "method": "POST",
                    "path": "/api/interop/start",
                    "body": {"moduleIds": module_ids},
                },
                **result,
            })
        except Exception as exc:
            return jsonify({"available": False, "error": str(exc)}), 502

    return app


# Manifest summary

# Build a compact ASLM_Module.json summary for GET /api/info.
def _manifest_summary() -> dict[str, Any]:
    """Build a compact ASLM_Module.json summary for GET /api/info."""

    manifest_path = _BASE_DIR / "ASLM_Module.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    # Summarize bridge, interop, and dependency sections for the info panel.
    bridge = manifest.get("downloadsBridge") or {}
    interop = manifest.get("moduleInterop") or {}
    deps = manifest.get("dependencies") or {}

    return {
        "id": manifest.get("id"),
        "name": manifest.get("name"),
        "version": manifest.get("version"),
        "type": manifest.get("type"),
        "author": manifest.get("author"),
        "hasPage": manifest.get("hasPage"),
        "downloadsBridge": {
            "protocolVersion": bridge.get("protocolVersion"),
            "entryPoint": bridge.get("entryPoint"),
            "operations": bridge.get("operations", []),
            "categories": bridge.get("categories", []),
            "targets": bridge.get("targets", {}),
        },
        "moduleInterop": {
            "protocolVersion": interop.get("protocolVersion"),
            "clientEnabled": (interop.get("client") or {}).get("enabled"),
        },
        "dependencies": deps,
        "settingsCount": len(manifest.get("settings") or []),
        "settingTypes": sorted({
            str(s.get("type", "string"))
            for s in (manifest.get("settings") or [])
        }),
    }
