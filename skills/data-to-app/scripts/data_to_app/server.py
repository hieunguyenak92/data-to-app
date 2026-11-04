"""Bounded loopback HTTP runtime for generated operational data apps."""
from __future__ import annotations

import argparse
import base64
import binascii
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit

from .engine import DataError, RevisionConflict, Store
from .io import read_table

MAX_UPLOAD = 10 * 1024 * 1024
MAX_BODY = 15 * 1024 * 1024
VERSION = "0.1.0"


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, app_root):
        self.app_root = Path(app_root).resolve()
        self.store = Store(self.app_root / ".data" / "app.sqlite")
        self.csrf_token = secrets.token_urlsafe(32)
        self.pending = {}
        self.pending_lock = threading.Lock()
        try:
            super().__init__(address, Handler)
        except BaseException:
            self.store.close()
            raise

    def server_close(self):
        super().server_close()
        close = getattr(self.store, "close", None)
        if close:
            close()


class Handler(BaseHTTPRequestHandler):
    server_version = "DataToApp/0.1"
    sys_version = ""

    def log_message(self, format, *args):
        # Avoid writing uploaded filenames, search queries or row values into console logs.
        pass

    def _send(self, status, body, content_type="application/json; charset=utf-8", headers=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status, message, code="request_error"):
        self._send(status, {"error": code, "message": message})

    def _host_ok(self):
        port = self.server.server_address[1]
        return self.headers.get("Host", "").lower() in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _query(self):
        parsed = urlsplit(self.path)
        if parsed.scheme or parsed.netloc:
            raise DataError("Use a relative application URL.")
        return parsed.path, parse_qs(parsed.query, keep_blank_values=True)

    @staticmethod
    def _one(query, name, default=""):
        return query.get(name, [default])[0]

    def do_GET(self):
        if not self._host_ok():
            return self._error(403, "Open the printed loopback URL.", "invalid_host")
        try:
            path, query = self._query()
            store = self.server.store
            if path == "/api/bootstrap":
                with store.read_snapshot():
                    summary = store.summary()
                    result = {"title": store.manifest().get("title", "Data workspace"),
                        "revision": summary["revision"], "summary": summary, "tables": store.tables(),
                        "csrf_token": self.server.csrf_token, "version": VERSION}
                return self._send(200, result)
            if path == "/api/rows":
                offset = int(self._one(query, "offset", "0"))
                limit = int(self._one(query, "limit", "50"))
                if offset < 0 or limit < 1 or limit > 200:
                    raise DataError("Use offset >= 0 and limit between 1 and 200.")
                search = self._one(query, "search")
                if len(search) > 512:
                    raise DataError("Search is limited to 512 characters.")
                return self._send(200, store.rows(self._one(query, "table"), search=search,
                    view=self._one(query, "view") or None,
                    include_missing=self._one(query, "missing", "0") == "1", offset=offset, limit=limit))
            if path == "/api/row":
                return self._send(200, store.get_row(self._one(query, "table"), self._one(query, "id")))
            if path == "/api/conflicts":
                with store.read_snapshot():
                    result = {"conflicts": store.conflicts(), "revision": store.summary()["revision"]}
                return self._send(200, result)
            if path == "/api/history":
                with store.read_snapshot():
                    result = {"history": store.history(), "revision": store.summary()["revision"]}
                return self._send(200, result)
            if path == "/api/export":
                table_id = self._one(query, "table")
                content = store.export_csv(table_id).encode("utf-8-sig")
                # Table IDs are validated by the model/store, but filenames remain conservative.
                filename = "".join(c for c in table_id if c.isascii() and (c.isalnum() or c in "_-"))[:64]
                return self._send(200, content, "text/csv; charset=utf-8",
                    {"Content-Disposition": f'attachment; filename="{filename or "table"}.csv"'})
            asset_map = {"/": "index.html", "/index.html": "index.html", "/style.css": "style.css",
                         "/app.js": "app.js", "/icon.svg": "icon.svg", "/favicon.ico": "icon.svg"}
            if path not in asset_map:
                return self._error(404, "This page was not found.", "not_found")
            target = self.server.app_root / "assets" / asset_map[path]
            if not target.is_file() or target.is_symlink():
                return self._error(404, "This asset was not found.", "not_found")
            mime = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                    ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}[target.suffix]
            self._send(200, target.read_bytes(), mime)
        except RevisionConflict as exc:
            self._error(409, str(exc), "revision_conflict")
        except (DataError, ValueError, KeyError, TypeError) as exc:
            self._error(400, str(exc), "invalid_input")
        except (OSError, RuntimeError, sqlite3.Error):
            self._error(500, "The local app could not complete this request.", "runtime_error")

    def _json_body(self):
        if self.headers.get("Transfer-Encoding"):
            raise DataError("Chunked request bodies are unsupported.")
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise DataError("Send application/json.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise DataError("Invalid Content-Length.") from exc
        if length < 1 or length > MAX_BODY:
            raise DataError("Request body exceeds the 15 MiB limit or is empty.")
        self.connection.settimeout(15)
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise DataError("Incomplete request body.")
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise DataError("Invalid JSON body.") from exc
        if not isinstance(body, dict):
            raise DataError("Send a JSON object.")
        return body

    @staticmethod
    def _revision(body):
        value = body.get("revision")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DataError("Include the current integer revision.")
        return value

    def do_POST(self):
        if not self._host_ok():
            return self._error(403, "Open the printed loopback URL.", "invalid_host")
        port = self.server.server_address[1]
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:
            return self._error(403, "This app accepts changes from its own page.", "invalid_origin")
        token = self.headers.get("X-DTA-Token", "")
        if not token.isascii() or not secrets.compare_digest(token, self.server.csrf_token):
            return self._error(403, "Refresh the app before making changes.", "invalid_token")
        try:
            path, _ = self._query()
            body = self._json_body()
            store = self.server.store
            if path == "/api/edit":
                result = store.edit_row(body.get("table"), body.get("row"), body.get("values"), self._revision(body))
                return self._send(200, result)
            if path == "/api/conflicts/resolve":
                result = store.resolve_conflict(body.get("id"), body.get("choice"), self._revision(body))
                return self._send(200, result)
            if path == "/api/import/preview":
                table_id = body.get("table")
                model = next((table for table in store.tables() if table["id"] == table_id), None)
                if model is None:
                    raise DataError("Choose an existing table for this import.")
                filename = body.get("filename", "")
                encoded = body.get("content_base64", "")
                if not isinstance(filename, str) or len(filename) > 255 or not isinstance(encoded, str):
                    raise DataError("Choose a CSV or XLSX file.")
                suffix = Path(filename).suffix.lower()
                if suffix not in {".csv", ".xlsx"}:
                    raise DataError("Choose a CSV or XLSX file.")
                try:
                    content = base64.b64decode(encoded, validate=True)
                except (ValueError, binascii.Error) as exc:
                    raise DataError("The uploaded file is not valid base64.") from exc
                if not content or len(content) > MAX_UPLOAD:
                    raise DataError("Choose a nonempty file of at most 10 MiB.")
                with tempfile.TemporaryDirectory(prefix="dta-upload-") as directory:
                    upload = Path(directory) / ("upload" + suffix)
                    upload.write_bytes(content)
                    table = read_table(upload, sheet=model.get("sheet"))
                table["source"] = Path(filename).name
                preview = store.preview_import(body.get("table"), table)
                pending_token = secrets.token_urlsafe(24)
                with self.server.pending_lock:
                    now = time.monotonic()
                    self.server.pending = {k: v for k, v in self.server.pending.items() if now - v[0] < 600}
                    if len(self.server.pending) >= 4:
                        oldest = min(self.server.pending, key=lambda k: self.server.pending[k][0])
                        del self.server.pending[oldest]
                    self.server.pending[pending_token] = (now, body.get("table"), table, preview["revision"])
                return self._send(200, {**preview, "token": pending_token})
            if path == "/api/import/apply":
                pending_token = body.get("token")
                if not isinstance(pending_token, str):
                    raise DataError("Preview the import before applying it.")
                with self.server.pending_lock:
                    pending = self.server.pending.get(pending_token)
                    if pending is None or time.monotonic() - pending[0] >= 600:
                        raise DataError("This import preview expired. Preview the file again.")
                    if self._revision(body) != pending[3]:
                        raise RevisionConflict("The preview revision changed. Preview the file again.")
                    result = store.apply_import(pending[1], pending[2], pending[3])
                    del self.server.pending[pending_token]
                return self._send(200, result)
            self._error(404, "This action was not found.", "not_found")
        except RevisionConflict as exc:
            self._error(409, str(exc), "revision_conflict")
        except (DataError, ValueError, KeyError, TypeError, TimeoutError) as exc:
            self._error(400, str(exc), "invalid_input")
        except (OSError, RuntimeError, sqlite3.Error):
            self._error(500, "The local app could not complete this request.", "runtime_error")

    def do_OPTIONS(self):
        self._error(405, "Cross-origin access is not enabled.", "method_not_allowed")


def main(app_root=None):
    parser = argparse.ArgumentParser(description="Run a local Data to App workspace.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("Use a port between 0 and 65535.")
    root = Path(app_root or Path.cwd()).resolve()
    if not (root / ".data" / "app.sqlite").is_file():
        parser.error("This directory has no generated app database. Build an app first.")
    try:
        server = AppServer(("127.0.0.1", args.port), root)
    except OSError as exc:
        parser.error(f"Cannot open local port: {exc}")
    port = server.server_address[1]
    print(f"Data to App {VERSION} · http://127.0.0.1:{port}", flush=True)
    print("Local workspace. Keep this process running; Ctrl+C stops it.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
