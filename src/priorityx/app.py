"""Loopback-only saved-result workspace and self-contained HTML builder.

The service keeps a single result bundle in memory. It never fits models, serves
arbitrary files, writes canonical results, or exposes a remotely bindable server.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import io
import json
import multiprocessing
from pathlib import Path
from socketserver import TCPServer
import threading
import tempfile
from typing import Any
from urllib.parse import quote
import webbrowser

from .results import ResultBundle, ResultValidationError, import_results_csv, strict_json_loads
from .views import prepare_bundle, resolve_settings

MAX_BODY_BYTES = 64 * 1024 * 1024
STATIC_TIMEOUT_SECONDS = 30


def _embedded(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def build_html(bundle: ResultBundle, settings=None, *, service_mode: bool = False) -> str:
    """Build offline HTML from packaged assets, with no Node or network step."""
    prepared = prepare_bundle(bundle)
    resolved = resolve_settings(settings, prepared)
    web = files("priorityx").joinpath("web")
    mark = web.joinpath("priorityx-mark.svg").read_text(encoding="utf-8")
    favicon = mark.replace('<g ', '<rect width="64" height="64" rx="12" fill="#f5f8f7"/><g ', 1)
    replacements = {"__LIBRARY__": web.joinpath("plotly-basic-4.1.2.min.js").read_text(encoding="utf-8"),
                    "__LOGO__": mark,
                    "__FAVICON__": "data:image/svg+xml," + quote(favicon, safe=""),
                    "__STYLE__": web.joinpath("style.css").read_text(encoding="utf-8"),
                    "__APP__": web.joinpath("app.js").read_text(encoding="utf-8"),
                    "__DATA__": _embedded({"bundle": bundle.to_dict(), "prepared": prepared}),
                    "__INITIAL__": _embedded(resolved.to_dict()),
                    "__SERVICE__": "true" if service_mode else "false"}
    template = web.joinpath("template.html").read_text(encoding="utf-8")
    # Replace only template tokens; user data or source text may contain tokens.
    import re
    return re.sub("|".join(re.escape(k) for k in replacements),
                  lambda match: replacements[match.group()], template)


def _static_worker(connection, dataset, settings, family, image_format):
    try:
        import matplotlib
        matplotlib.use("Agg")
        from .viz.export import render_static
        fig, report = render_static(dataset, settings, family)
        buffer = io.BytesIO()
        fig.savefig(buffer, format=image_format, dpi=settings.dpi,
                    metadata={"Description": json.dumps(report.to_dict(), ensure_ascii=False, allow_nan=False)})
        connection.send((True, buffer.getvalue(), report.to_dict()))
        fig.clear()
    except Exception as exc:
        connection.send((False, str(exc), None))
    finally:
        connection.close()


def _static_response(dataset, settings, family, image_format):
    context = multiprocessing.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(target=_static_worker,
                              args=(writer, dataset, settings, family, image_format), daemon=True)
    process.start()
    writer.close()
    try:
        if not reader.poll(STATIC_TIMEOUT_SECONDS):
            raise ResultValidationError("Static layout exceeded 30 seconds; reduce the displayed population or choose manual dimensions.")
        try:
            ok, value, report = reader.recv()
        except EOFError as exc:
            raise ResultValidationError("Static renderer stopped unexpectedly; retry with a smaller view.") from exc
        if not ok:
            raise ResultValidationError(f"Static rendering failed: {value}")
        return value, report
    finally:
        reader.close()
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
        if process.is_alive():
            process.kill()
            process.join(timeout=2)


def _import_payload(payload):
    allowed = {"entity_type", "type_label", "cadence", "source_id", "coverage_start", "as_of", "files", "activate"}
    if set(payload) - allowed or not isinstance(payload.get("files"), dict) or not payload["files"]:
        raise ResultValidationError("Import requires metadata and a non-empty files object containing matrix, movement or transitions CSV roles.")
    kwargs = {key: payload.get(key) for key in allowed - {"files", "activate"}}
    with tempfile.TemporaryDirectory(prefix="priorityx-import-") as root:
        paths = {}
        for role, item in payload["files"].items():
            if role not in ("matrix", "movement", "transitions"):
                raise ResultValidationError(f"Unknown CSV role: {role}")
            if not isinstance(item, dict) or set(item) != {"name", "text"}:
                raise ResultValidationError(f"{role} file requires name and text only")
            name, text = item["name"], item["text"]
            if (not isinstance(name, str) or not name or name in (".", "..")
                    or "/" in name or "\\" in name or "\x00" in name or not isinstance(text, str)):
                raise ResultValidationError("CSV names must be basenames; contents must be UTF-8 text")
            directory = Path(root) / role
            directory.mkdir()
            path = directory / name
            path.write_text(text, encoding="utf-8", newline="")
            paths[role] = path
        return ResultBundle([import_results_csv(files=paths, **kwargs)])


class WorkspaceServer(ThreadingHTTPServer):
    """One in-memory private workspace; bind only to numeric loopback."""
    daemon_threads = True

    def __init__(self, bundle: ResultBundle | None = None, port: int = 0):
        self.bundle = ResultBundle.from_dict((bundle or ResultBundle()).to_dict())
        self.state_lock = threading.Lock()
        self.render_lock = threading.Lock()
        super().__init__(("127.0.0.1", port), WorkspaceHandler)

    def server_bind(self):
        # HTTPServer.server_bind calls getfqdn(), which can wait on a network
        # resolver even for loopback. This workspace uses a numeric local host.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_port}"


class WorkspaceHandler(BaseHTTPRequestHandler):
    server: WorkspaceServer
    protocol_version = "HTTP/1.0"

    def log_message(self, *_args):
        pass

    def _send(self, code, data, content_type="application/json; charset=utf-8", report=None):
        if isinstance(data, dict):
            data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'self'; font-src data:; frame-ancestors 'none'; base-uri 'none'")
        if report is not None:
            self.send_header("X-PriorityX-Layout", json.dumps(report, ensure_ascii=True, separators=(",", ":")))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _guard(self):
        expected = f"127.0.0.1:{self.server.server_port}"
        host = self.headers.get("Host", "")
        if host != expected:
            self._send(403, {"error": "Use the numeric loopback workspace URL."})
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin != self.server.url:
            self._send(403, {"error": "Cross-origin workspace requests are not allowed."})
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self._send(403, {"error": "Cross-site workspace requests are not allowed."})
            return False
        return True

    def do_GET(self):
        if not self._guard():
            return
        try:
            with self.server.state_lock:
                bundle = self.server.bundle
            if self.path == "/":
                self._send(200, build_html(bundle, service_mode=True), "text/html; charset=utf-8")
            elif self.path == "/api/bootstrap":
                self._send(200, {"bundle": bundle.to_dict(), "prepared": prepare_bundle(bundle)})
            else:
                self._send(404, {"error": "Unknown workspace route."})
        except (ValueError, OSError) as exc:
            self._send(400, {"error": str(exc)})

    def do_POST(self):
        if not self._guard():
            return
        if self.path not in ("/api/prepare", "/api/import", "/api/static"):
            self._send(404, {"error": "Unknown workspace route."})
            return
        try:
            if self.headers.get_content_type() != "application/json":
                raise ResultValidationError("Use application/json for workspace requests.")
            if self.headers.get("Transfer-Encoding"):
                raise ResultValidationError("Chunked request bodies are not supported.")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY_BYTES:
                self._send(413, {"error": "Request body must be between 1 byte and 64 MiB."})
                return
            self.connection.settimeout(15)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ResultValidationError("Incomplete request body.")
            payload = strict_json_loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ResultValidationError("Request JSON must be an object.")
            if self.path == "/api/import":
                bundle = _import_payload(payload)
            else:
                allowed = {"bundle", "bundle_json", "activate"} if self.path == "/api/prepare" else {"bundle", "settings", "family", "format"}
                if set(payload) - allowed:
                    raise ResultValidationError("Unknown request fields.")
                if "bundle" in payload and "bundle_json" in payload:
                    raise ResultValidationError("Provide bundle or bundle_json, not both.")
                value = strict_json_loads(payload["bundle_json"]) if "bundle_json" in payload else payload.get("bundle")
                bundle = ResultBundle.from_dict(value)
            prepared = prepare_bundle(bundle)
            if self.path == "/api/static":
                family, image_format = payload.get("family"), payload.get("format", "png")
                if family not in ("matrix", "timeline", "paths") or image_format not in ("png", "svg"):
                    raise ResultValidationError("Choose matrix/timeline/paths and png/svg.")
                settings = resolve_settings(payload.get("settings"), prepared)
                selected = next((d for d in prepared["datasets"] if d["entity_type"] == settings.entity_type and d["cadence"] == settings.cadence), None)
                if selected is None:
                    raise ResultValidationError("Open saved results before requesting a static chart.")
                if not self.server.render_lock.acquire(blocking=False):
                    self._send(409, {"error": "A static layout is already rendering; retry after it finishes."})
                    return
                try:
                    image, report = _static_response(selected, settings, family, image_format)
                finally:
                    self.server.render_lock.release()
                self._send(200, image, "image/png" if image_format == "png" else "image/svg+xml", report)
                return
            activate = payload.get("activate", False)
            if type(activate) is not bool:
                raise ResultValidationError("activate must be true or false")
            if activate:
                with self.server.state_lock:
                    self.server.bundle = bundle
            self._send(200, {"bundle": bundle.to_dict(), "prepared": prepared})
        except (ValueError, TypeError, KeyError, UnicodeError, OSError) as exc:
            self._send(400, {"error": str(exc)})


def main(argv=None):
    parser = argparse.ArgumentParser(description="PriorityX local saved-result workspace")
    sub = parser.add_subparsers(dest="command", required=True)
    app = sub.add_parser("app", help="Open a private loopback workspace")
    app.add_argument("--bundle", type=Path, help="Validated saved-result bundle JSON")
    app.add_argument("--port", type=int, default=0, help="Loopback port; 0 chooses a free port")
    app.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    try:
        bundle = ResultBundle.load(args.bundle) if args.bundle else ResultBundle()
        server = WorkspaceServer(bundle, args.port)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f"PriorityX workspace: {server.url}", flush=True)
    if not args.no_browser:
        webbrowser.open(server.url)
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
