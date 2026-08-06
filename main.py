from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path


# Prepare project imports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


# Lazy Flask application
class LazyFlaskApplication:
    """Bind the port before Flask loads so ASLM can reserve example-port immediately."""

    # Initialize loader state (app not created yet).
    def __init__(self) -> None:
        """Initialize loader state (app not created yet)."""

        self._application = None
        self._error: BaseException | None = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    # Start a daemon thread that imports and builds the Flask app.
    def load_in_background(self) -> None:
        """Start a daemon thread that imports and builds the Flask app."""

        thread = threading.Thread(
            target=self._load,
            name="aslm-example-flask-loader",
            daemon=True,
        )
        thread.start()

    # Import App.app.create_app once; store result or error for WSGI.
    def _load(self) -> None:
        """Import App.app.create_app once; store result or error for WSGI."""

        with self._lock:
            if self._application is not None or self._error is not None:
                return
            try:
                from App.app import create_app

                self._application = create_app()
            except BaseException as exc:
                self._error = exc
            finally:
                self._ready.set()

    # Serve requests: Flask app, startup error page, or loading placeholder.
    def __call__(self, environ, start_response):
        """Serve requests: Flask app, startup error page, or loading placeholder."""

        # Flask finished loading — delegate to the real application.
        if self._application is not None:
            return self._application(environ, start_response)

        # Import or create_app failed — return plain-text 500.
        if self._error is not None:
            body = f"ASLM-Example failed to start: {self._error}".encode("utf-8", errors="replace")
            start_response(
                "500 Internal Server Error",
                [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(body)))],
            )
            return [body]

        # Still loading — auto-refresh HTML so the WebView retries.
        body = (
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            "<meta http-equiv=\"refresh\" content=\"1\">"
            "<title>Example Python Module starting</title></head>"
            "<body style=\"font-family:Segoe UI,sans-serif;background:#111;color:#eee;\">"
            "Example Python Module is starting\u2026"
            "</body></html>"
        ).encode("utf-8")
        start_response(
            "503 Service Unavailable",
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Retry-After", "1"),
            ],
        )
        return [body]


# Run runserver
def cmd_runserver(port: int, log: bool) -> None:
    """Start the Flask UI server on the requested port."""

    if log:
        print(f"[ASLM-Example] Starting server on port {port}...")

    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

    class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
        """Serve requests concurrently."""

        daemon_threads = True

    class QuietWSGIRequestHandler(WSGIRequestHandler):
        """Suppress routine HTTP access logs in the ASLM console."""

        # Suppress per-request access log lines.
        def log_message(self, format: str, *args) -> None:
            return

    # Bind socket immediately; load Flask on a background thread.
    app = LazyFlaskApplication()
    with make_server(
        "127.0.0.1",
        port,
        app,
        server_class=ThreadedWSGIServer,
        handler_class=QuietWSGIRequestHandler,
    ) as httpd:
        app.load_in_background()
        if log:
            print(f"[ASLM-Example] UI server listening at http://127.0.0.1:{port}/", flush=True)
        httpd.serve_forever()


# Run first_run
def cmd_first_run(log: bool, ui_port: int) -> None:
    """Run Settings/first_run.py (settings.json only; venv is host-managed)."""

    from Settings.first_run import run as first_run

    first_run(log=log, ui_port=ui_port)


# Run get_setting
def cmd_get_setting(key: str) -> None:
    """Print one setting value to stdout for ASLM getExec."""

    from Settings.settings import get

    value = get(key)
    print(value if value is not None else "")


# Run set_setting
def cmd_set_setting(key: str, value: str) -> None:
    """Parse {value} and persist one setting for ASLM setExec."""

    from Settings.settings import normalize_setting_value, set as settings_set

    parsed = normalize_setting_value(value)
    settings_set(key, parsed)
    print(f"[ASLM-Example] Setting '{key}' updated to {parsed!r}")


# Run apply_aslm_host_theme
def cmd_apply_aslm_host_theme(theme_file: str) -> None:
    """Load host theme JSON from --file and write Settings/host_theme.json."""

    from Settings.host_theme import save_host_theme_payload

    # Read temp file written by ASLM before setExec.
    path = Path(theme_file)
    if not path.is_file():
        print(f"Error: theme file not found: {theme_file}")
        sys.exit(1)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: could not read theme file: {exc}")
        sys.exit(1)

    # .NET may write UTF-8 with BOM; strip it before JSON parsing.
    raw = raw.lstrip("\ufeff").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in theme file: {exc}")
        sys.exit(1)
    if not isinstance(data, dict):
        print("Error: host theme JSON must be an object.")
        sys.exit(1)

    save_host_theme_payload(data)
    print("[ASLM-Example] Host theme snapshot updated.")


# Run apply_aslm_locale
def cmd_apply_aslm_locale(locale_file: str) -> None:
    """Load host locale JSON from --file and write Settings/host_locale.json."""

    from Settings.host_locale import save_host_locale_payload

    path = Path(locale_file)
    if not path.is_file():
        print(f"Error: locale file not found: {locale_file}")
        sys.exit(1)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: could not read locale file: {exc}")
        sys.exit(1)

    raw = raw.lstrip("\ufeff").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in locale file: {exc}")
        sys.exit(1)
    if not isinstance(data, dict):
        print("Error: host locale JSON must be an object.")
        sys.exit(1)

    save_host_locale_payload(data)
    print("[ASLM-Example] Host locale snapshot updated.")


# Run downloads_bridge
def cmd_downloads_bridge() -> None:
    """Dispatch one bridge request from stdin and print the JSON response."""

    from Services.downloads_bridge import run_cli

    raise SystemExit(run_cli())


# CLI parser
def _build_parser() -> argparse.ArgumentParser:
    """Return the argparse definition for main.py."""

    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Example Python Module — ASLM command entry point",
    )
    parser.add_argument("command", type=str, help="Command to execute")
    parser.add_argument("--port", type=int, default=20100, help="Port for runserver (default: 20100)")
    parser.add_argument("--key", type=str, default=None, help="Setting key for get_setting/set_setting")
    parser.add_argument("--value", type=str, default=None, help="Setting value for set_setting")
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to JSON payload for apply_aslm_host_theme or apply_aslm_locale",
    )
    parser.add_argument("--log", action="store_true", help="Enable verbose output")
    return parser


# Startup banner
def _maybe_print_banner(command: str) -> None:
    """Print the module name for commands that are not machine-readable hooks."""

    # Hooks that must emit only machine-readable stdout.
    silent = {
        "get_setting",
        "set_setting",
        "downloads_bridge",
        "apply_aslm_host_theme",
        "apply_aslm_locale",
    }
    if command not in silent:
        try:
            manifest_path = Path(BASE_DIR) / "ASLM_Module.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                name = manifest.get("name", "Example Python Module")
                version = manifest.get("version", "")
                print(f"[ASLM-Example] {name} v{version}")
        except Exception:
            pass


# Port resolution
def _resolve_runserver_port(requested_port: int) -> int:
    """Prefer CLI port, then ASLM_UI_PORT, then settings.json example-port."""

    # Explicit CLI override (not the default 20100 placeholder).
    if requested_port != 20100:
        return requested_port

    # Host-injected port when ASLM starts runserver.
    env_port = os.environ.get("ASLM_UI_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass

    # Fall back to persisted settings.
    try:
        from Settings.settings import load_settings

        runtime_settings = load_settings()
        return int(runtime_settings.get("example-port", 20100))
    except Exception:
        return 20100


# Main entry
def main() -> None:
    """Parse argv and dispatch the requested command."""

    parser = _build_parser()
    args = parser.parse_args()

    _maybe_print_banner(args.command)

    match args.command:
        case "runserver":
            port = _resolve_runserver_port(args.port)
            cmd_runserver(port, log=args.log)

        case "first_run":
            cmd_first_run(log=True, ui_port=args.port)

        case "get_setting":
            if not args.key:
                print("Error: --key argument is required.")
                sys.exit(1)
            cmd_get_setting(args.key)

        case "set_setting":
            if not args.key or args.value is None:
                print("Error: --key and --value arguments are required.")
                sys.exit(1)
            cmd_set_setting(args.key, args.value)

        case "apply_aslm_host_theme":
            if not args.file:
                print("Error: --file argument is required.")
                sys.exit(1)
            cmd_apply_aslm_host_theme(args.file)

        case "apply_aslm_locale":
            if not args.file:
                print("Error: --file argument is required.")
                sys.exit(1)
            cmd_apply_aslm_locale(args.file)

        case "downloads_bridge":
            cmd_downloads_bridge()

        case "help":
            parser.print_help()

        case _:
            print(f"[ASLM-Example] Unknown command: '{args.command}'")
            print("Run 'python main.py help' for usage.")
            sys.exit(1)


if __name__ == "__main__":
    main()
