from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

# Interop API reference
# Mirrors AslmModuleInteropServer routes for the reference dashboard.
INTEROP_API_SPEC: dict[str, Any] = {
    "protocolVersion": 1,
    "baseUrlEnv": "ASLM_MODULE_INTEROP_BASE_URL",
    "portEnv": "ASLM_MODULE_INTEROP_PORT",
    "constraints": [
        "Loopback clients only (127.0.0.1 / ::1).",
        "Caller module must be running before POST /v1/modules/start.",
    ],
    "endpoints": [
        {
            "method": "GET",
            "path": "/v1/registry",
            "summary": "List installed and running module snapshots with port/host data.",
            "requestBody": None,
            "successStatus": 200,
            "responseFields": {
                "interopBaseUrl": "Loopback root URL of this listener.",
                "aslmApi": "AslmApiDto — ASLM API mirror server state.",
                "installedModules": "Array of InstalledModuleDto.",
                "runningModules": "Array of RunningModuleDto with hosts.",
            },
            "installedModuleFields": [
                "id", "name", "version", "installed", "enabled",
                "firstRunCompleted", "hasRunCommands", "hasMultipleInstances",
                "instanceFolder",
            ],
            "runningModuleFields": [
                "id", "name", "instanceFolder", "sourcePath", "pageUrl", "hosts",
            ],
            "moduleHostFields": ["hostKey", "routeKey", "port", "targetUrl", "mirrorUrl"],
            "aslmApiFields": ["enabled", "running", "port", "baseUrl"],
            "errorResponses": [],
        },
        {
            "method": "GET",
            "path": "/v1/ports",
            "summary": "Return ASLM API state and port/host data for running modules only.",
            "requestBody": None,
            "successStatus": 200,
            "responseFields": {
                "aslmApi": "AslmApiDto — ASLM API mirror server state.",
                "runningModules": "Array of RunningModuleDto with hosts.",
            },
            "runningModuleFields": [
                "id", "name", "instanceFolder", "sourcePath", "pageUrl", "hosts",
            ],
            "moduleHostFields": ["hostKey", "routeKey", "port", "targetUrl", "mirrorUrl"],
            "aslmApiFields": ["enabled", "running", "port", "baseUrl"],
            "errorResponses": [],
        },
        {
            "method": "POST",
            "path": "/v1/modules/start",
            "summary": "Start or ensure running state for one or more modules.",
            "requestBody": {
                "callerModuleId": "string — id of the running module making the call",
                "moduleIds": ["string — module ids to start"],
            },
            "successStatus": 200,
            "responseFields": {
                "results": "Array of { moduleId, status, message? }.",
            },
            "resultStatuses": [
                "started",
                "alreadyRunning",
                "notFound",
                "noRunCommands",
                "firstRunFailed",
                "error",
            ],
            "errorResponses": [
                {"status": 400, "code": "bad_request", "message": "JSON body / callerModuleId / moduleIds invalid."},
                {"status": 403, "code": "caller_not_running", "message": "callerModuleId is not a running module."},
                {"status": 403, "code": "forbidden", "message": "Non-loopback client."},
                {"status": 404, "code": "not_found", "message": "Unknown route."},
                {"status": 500, "code": "error", "message": "Internal server error."},
            ],
        },
    ],
}


# Return the interop base URL from ASLM_MODULE_INTEROP_BASE_URL.
def _base_url() -> str:
    """Return the interop base URL from ASLM_MODULE_INTEROP_BASE_URL."""

    url = (os.environ.get("ASLM_MODULE_INTEROP_BASE_URL") or "").strip()
    if not url:
        raise RuntimeError(
            "ASLM_MODULE_INTEROP_BASE_URL is not set. "
            "Ensure moduleInterop.client.enabled is true in ASLM_Module.json "
            "and that this module was launched by ASLM."
        )
    return url.rstrip("/") + "/"


# HTTP exchange

# Perform one request and capture metadata for the dashboard exchange log.
def _http_exchange(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    timeout: int = 120,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (response_body, exchange_metadata) for one interop HTTP call."""

    url = _base_url() + path.lstrip("/")
    headers: dict[str, str] = {}
    data: bytes | None = None

    # Serialize JSON body for POST endpoints.
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method, headers=headers)

    # Metadata returned to the dashboard exchange log.
    exchange: dict[str, Any] = {
        "method": method,
        "url": url,
        "requestHeaders": headers,
        "requestBody": body,
        "statusCode": None,
        "responseBody": None,
    }

    try:
        # Success path — parse JSON body from the host.
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            exchange["statusCode"] = resp.status
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                parsed = {"value": parsed}
            exchange["responseBody"] = parsed
            return parsed, exchange
    except urllib.error.HTTPError as exc:
        # Still return parsed error JSON so the UI can show 4xx/5xx bodies.
        exchange["statusCode"] = exc.code
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(payload)
            if not isinstance(parsed, dict):
                parsed = {"value": parsed}
        except json.JSONDecodeError:
            parsed = {"raw": payload}
        exchange["responseBody"] = parsed
        return parsed, exchange


# Return the GET /v1/registry payload.
def get_registry() -> dict[str, Any]:
    """Return the GET /v1/registry payload."""

    data, _exchange = get_registry_exchange()
    return data


# Call GET /v1/registry and include exchange metadata.
def get_registry_exchange() -> tuple[dict[str, Any], dict[str, Any]]:
    """Call GET /v1/registry and include exchange metadata."""

    return _http_exchange("GET", "v1/registry", None, timeout=30)


# Return the POST /v1/modules/start payload.
def request_start(*, caller_module_id: str, module_ids: list[str]) -> dict[str, Any]:
    """Return the POST /v1/modules/start payload."""

    data, _exchange = request_start_exchange(
        caller_module_id=caller_module_id,
        module_ids=module_ids,
    )
    return data


# Call POST /v1/modules/start and include exchange metadata.
def request_start_exchange(
    *,
    caller_module_id: str,
    module_ids: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Call POST /v1/modules/start and include exchange metadata."""

    body = {
        "callerModuleId": caller_module_id,
        "moduleIds": list(module_ids),
    }
    return _http_exchange("POST", "v1/modules/start", body, timeout=120)


# Return the GET /v1/ports payload.
def get_ports() -> dict[str, Any]:
    """Return the GET /v1/ports payload (ASLM API state and running module hosts)."""

    data, _exchange = get_ports_exchange()
    return data


# Call GET /v1/ports and include exchange metadata.
def get_ports_exchange() -> tuple[dict[str, Any], dict[str, Any]]:
    """Call GET /v1/ports and include exchange metadata."""

    return _http_exchange("GET", "v1/ports", None, timeout=30)


# Return whether ASLM_MODULE_INTEROP_BASE_URL is set.
def is_available() -> bool:
    """Return whether ASLM_MODULE_INTEROP_BASE_URL is set."""

    return bool((os.environ.get("ASLM_MODULE_INTEROP_BASE_URL") or "").strip())
