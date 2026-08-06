from __future__ import annotations

import json
import sys
from typing import Any

# Bridge configuration
# ASLM spawns main.py downloads_bridge: one JSON request on stdin, one response on stdout.
PROTOCOL_VERSION = 1
CATEGORY_ID = "example-catalog"
GROUP_KEY = "python-reference"
TARGET_REF = "example_data"


# Response helpers

# Build a standard bridge response payload.
def _response(
    *,
    success: bool = True,
    categories: list[dict[str, Any]] | None = None,
    items: list[dict[str, Any]] | None = None,
    filters: list[dict[str, Any]] | None = None,
    item_detail: dict[str, Any] | None = None,
    install_manifest: dict[str, Any] | None = None,
    uninstall_manifest: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Return a response payload that matches the bridge contract."""

    payload: dict[str, Any] = {
        "protocolVersion": PROTOCOL_VERSION,
        "success": success,
        "warnings": warnings or [],
    }
    # Include only the fields relevant to the current operation.
    if categories is not None:
        payload["categories"] = categories
    if items is not None:
        payload["items"] = items
    if filters is not None:
        payload["filters"] = filters
    if item_detail is not None:
        payload["itemDetail"] = item_detail
    if install_manifest is not None:
        payload["installManifest"] = install_manifest
    if uninstall_manifest is not None:
        payload["uninstallManifest"] = uninstall_manifest
    if error:
        payload["error"] = error
    return payload


# Stdin reader

# Read one JSON object from stdin.
def _read_request() -> dict[str, Any]:
    """Read one JSON object from stdin."""

    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


# Reference catalog

# Return categories for list_categories.
def _demo_categories() -> list[dict[str, Any]]:
    """Return categories for list_categories."""

    return [
        {
            "id": CATEGORY_ID,
            "title": "Python reference artifacts",
            "description": (
                "Documents downloads bridge v1 operations. "
                "Items map to targetRef example_data → Data/example-downloads/."
            ),
            "groupKey": GROUP_KEY,
            "targetRef": TARGET_REF,
            "sortOrder": 10,
        }
    ]


# Return items for list_items.
def _demo_items() -> list[dict[str, Any]]:
    """Return items for list_items."""

    return [
        {
            "resourceKey": "example:hello-world",
            "categoryId": CATEGORY_ID,
            "groupKey": GROUP_KEY,
            "title": "Flask WebView UI (this module)",
            "summary": "Served by main.py runserver on setting example-port; WebView loads http://127.0.0.1:<port>/.",
            "provider": "NEXTGGTECH",
            "version": "1.0.0",
            "homepageUrl": "https://github.com/NEXTGGTECH/ASLM-Python-Example-Module",
            "detail": (
                "Represents the module page (App/). resolve_install returns an empty steps[] "
                "array here so no files are written — copy the manifest shape for real "
                "download_file / extract_zip / python_package steps."
            ),
            "tags": ["reference", "flask", "ui"],
            "variantCount": 1,
            "defaultVariantResourceKey": "example:hello-world:latest",
            "sortOrder": 0,
        },
        {
            "resourceKey": "example:sample-package",
            "categoryId": CATEGORY_ID,
            "groupKey": GROUP_KEY,
            "title": "Host venv dependencies",
            "summary": "flask>=3.0 from dependencies.engines[].libraries → Engines/Python/venv-aslm-python-example/.",
            "provider": "NEXTGGTECH",
            "version": "1.0.0",
            "homepageUrl": "https://github.com/NEXTGGTECH/ASLM-Python-Example-Module/blob/main/ASLM_Module.json",
            "detail": (
                "ASLM installs pip packages on first-run into the managed venv "
                "(ASLM_ENGINE_ENV_DIR). describe_item exposes variants to show how "
                "resourceKey suffixes select install manifests."
            ),
            "tags": ["reference", "python-runtime", "venv"],
            "variantCount": 2,
            "defaultVariantResourceKey": "example:sample-package:stable",
            "sortOrder": 1,
        },
    ]


# Look up a catalog item by resourceKey.
def _find_item(resource_key: str) -> dict[str, Any] | None:
    """Look up a catalog item by resourceKey."""

    for item in _demo_items():
        if item["resourceKey"] == resource_key:
            return item
    return None


# Operation handlers

# Handle list_categories.
def _handle_list_categories() -> dict[str, Any]:
    """Handle list_categories."""

    return _response(categories=_demo_categories())


# Handle list_items.
def _handle_list_items(category_id: str) -> dict[str, Any]:
    """Handle list_items."""

    if category_id and category_id != CATEGORY_ID:
        return _response(success=False, error=f"Unsupported categoryId: {category_id!r}")

    return _response(
        items=_demo_items(),
        filters=[
            {
                "key": "reference-only",
                "title": "Reference entries",
                "kind": "tag",
                "selected": True,
                "sortOrder": 0,
            }
        ],
        warnings=[
            "Reference catalog: resolve_install / resolve_uninstall return empty steps[] — inspect JSON shape only."
        ],
    )


# Handle describe_item.
def _handle_describe_item(category_id: str, resource_key: str) -> dict[str, Any]:
    """Handle describe_item."""

    if category_id and category_id != CATEGORY_ID:
        return _response(success=False, error=f"Unsupported categoryId: {category_id!r}")
    if not resource_key:
        return _response(success=False, error="Missing resourceKey for describe_item.")

    item = _find_item(resource_key)
    if item is None:
        return _response(success=False, error=f"Unknown resourceKey: {resource_key!r}")

    detail = dict(item)

    # Attach variant rows — shape differs for single- vs multi-variant items.
    if resource_key == "example:hello-world":
        detail["variants"] = [
            {
                "resourceKey": "example:hello-world:latest",
                "title": "main branch",
                "summary": "Tracks ASLM_Module.json version 1.0.0 (module page + bridge).",
                "version": "1.0.0",
                "sortOrder": 0,
            }
        ]
    else:
        detail["variants"] = [
            {
                "resourceKey": f"{resource_key}:stable",
                "title": "Release channel",
                "summary": "Matches update.channel=release in the manifest.",
                "version": "1.0.0",
                "sortOrder": 0,
            },
            {
                "resourceKey": f"{resource_key}:beta",
                "title": "Pre-release",
                "summary": "Hypothetical beta venv pin for testing allowedValues-style pins.",
                "version": "1.1.0-beta",
                "sortOrder": 1,
            },
        ]

    return _response(item_detail=detail)


# Handle resolve_install.
def _handle_resolve_install(category_id: str, resource_key: str) -> dict[str, Any]:
    """Handle resolve_install."""

    if category_id and category_id != CATEGORY_ID:
        return _response(success=False, error=f"Unsupported categoryId: {category_id!r}")
    if not resource_key:
        return _response(success=False, error="Missing resourceKey for resolve_install.")

    item = _find_item(resource_key.rsplit(":", 1)[0]) or _find_item(resource_key)
    title = str(item["title"]) if item else resource_key

    return _response(
        install_manifest={
            "resourceKey": resource_key,
            "categoryId": CATEGORY_ID,
            "targetRef": TARGET_REF,
            "title": title,
            "message": "Reference manifest — steps[] is empty. Add download_file, extract_zip, or python_package objects for real installs.",
            "steps": [],
        },
        warnings=[
            "Example step types: {\"type\":\"download_file\",\"url\":\"...\",\"dest\":\"file.zip\"}, "
            "{\"type\":\"extract_zip\",\"src\":\"file.zip\",\"dest\":\".\"}, "
            "{\"type\":\"python_package\",\"package\":\"flask\"}."
        ],
    )


# Handle resolve_uninstall.
def _handle_resolve_uninstall(category_id: str, resource_key: str) -> dict[str, Any]:
    """Handle resolve_uninstall."""

    if category_id and category_id != CATEGORY_ID:
        return _response(success=False, error=f"Unsupported categoryId: {category_id!r}")
    if not resource_key:
        return _response(success=False, error="Missing resourceKey for resolve_uninstall.")

    return _response(
        uninstall_manifest={
            "resourceKey": resource_key,
            "categoryId": CATEGORY_ID,
            "targetRef": TARGET_REF,
            "message": "Reference uninstall — steps[] empty. Host removes files under targetRef when steps are provided.",
            "steps": [],
        },
        warnings=[
            "Uninstall steps typically mirror install paths (delete file/tree) — see ASLM DownloadInstaller docs."
        ],
    )


# Dispatcher

# Route one stdin request to the matching operation handler.
def dispatch(request: dict[str, Any]) -> dict[str, Any]:
    """Route one stdin request to the matching operation handler."""

    operation = str(request.get("operation") or "").strip().lower()
    category_id = str(request.get("categoryId") or "").strip()
    resource_key = str(request.get("resourceKey") or "").strip()

    # Route to the handler named in ASLM_Module.json downloadsBridge.operations.
    if operation == "list_categories":
        return _handle_list_categories()
    if operation == "list_items":
        return _handle_list_items(category_id)
    if operation == "describe_item":
        return _handle_describe_item(category_id, resource_key)
    if operation == "resolve_install":
        return _handle_resolve_install(category_id, resource_key)
    if operation == "resolve_uninstall":
        return _handle_resolve_uninstall(category_id, resource_key)

    return _response(
        success=False,
        error=f"Unsupported downloads bridge operation: {operation!r}",
    )


# CLI entry point

# Read stdin, dispatch, and print one JSON response (main.py downloads_bridge).
def run_cli() -> int:
    """Read stdin, dispatch, and print one JSON response (used by main.py downloads_bridge)."""

    try:
        response = dispatch(_read_request())
    except Exception as exc:
        response = _response(success=False, error=str(exc))

    print(json.dumps(response, ensure_ascii=True))
    return 0


# Dashboard helper

# Run one operation in-process for GET /api/downloads.
def demo_dispatch(operation: str, **kwargs: Any) -> dict[str, Any]:
    """Run one operation in-process for GET /api/downloads."""

    return dispatch({"operation": operation, **kwargs})
