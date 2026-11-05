"""Optional local server: an index of every page, plus the pages. Localhost only, read only."""

from __future__ import annotations

import json
import mimetypes
import re
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .pages import SAVED_DIR, PageError, iter_pages, list_saved, load_page_dir, pages_root, prune_pages, public_url
from .pdf import find_chrome, render_pdf
from .profiles import builtin_dir

_LOCAL_HOST = re.compile(r"^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")
_PAGE_PATH = re.compile(r"^/p/([a-z0-9-]+)/([a-z0-9-]+)(/.*)?$")
_SAVED_PATH = re.compile(r"^/saved/([a-z0-9-]+\.html)$")
_INTERNAL_FILES = {"page.toml", "content.html"}
# What a phone needs to install the index as an app.
_APP_FILES = {
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/icon-192.png": ("icon-192.png", "image/png"),
    "/icon-512.png": ("icon-512.png", "image/png"),
}
_PRUNE_INTERVAL_SECONDS = 600.0
_PDF_PATH = re.compile(r"^/api/pdf/([a-z0-9-]+)/([a-z0-9-]+)$")
_MAX_STATE_BYTES = 2_000_000


def _index_html() -> bytes:
    template = resources.files("pagekit").joinpath("static/index.html").read_text()
    theme = (builtin_dir() / "theme.css").read_text()
    return template.replace("{{theme}}", theme).encode()


def _resolve_page_file(profile: str, slug: str, relative: str) -> Path | None:
    if profile == SAVED_DIR:
        return None
    page_dir = (pages_root() / profile / slug).resolve()
    target = (page_dir / unquote(relative).lstrip("/")).resolve()
    if not target.is_relative_to(page_dir) or not (page_dir / "page.toml").is_file():
        return None
    if target.parent == page_dir and target.name in _INTERNAL_FILES:
        return None
    return target if target.is_file() else None


def make_handler():
    index = _index_html()

    class Handler(BaseHTTPRequestHandler):
        server_version = "pagekit"

        def log_message(self, fmt, *args):
            pass

        def _send(self, status: int, body: bytes = b"", ctype: str = "application/json", extra=None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if body and self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload) -> None:
            self._send(status, json.dumps(payload).encode())

        def _file(self, path: Path) -> None:
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if ctype.startswith("text/"):
                ctype += "; charset=utf-8"
            self._send(200, path.read_bytes(), ctype)

        def _guard(self) -> bool:
            """Block DNS rebinding and cross-site reads."""
            host = self.headers.get("Host", "")
            # The one extra name the user set up. Everything else stays localhost only.
            public_host = urlsplit(public_url()).netloc
            if not _LOCAL_HOST.match(host) and host != public_host:
                self._json(403, {"error": "forbidden host"})
                return False
            origin = self.headers.get("Origin")
            if origin and urlsplit(origin).netloc not in {host, public_host}:
                self._json(403, {"error": "forbidden origin"})
                return False
            return True

        def do_GET(self):
            if not self._guard():
                return
            path = urlsplit(self.path).path
            if path == "/":
                return self._send(200, index, "text/html; charset=utf-8")
            if path in _APP_FILES:
                name, ctype = _APP_FILES[path]
                return self._send(200, resources.files("pagekit").joinpath("static", name).read_bytes(), ctype)
            if path == "/api/pdf":
                return self._json(200, {"available": bool(find_chrome())})
            if path == "/api/pages":
                return self._json(200, [p.to_json() for p in iter_pages() if p.index.is_file()] + list_saved())
            if match := _SAVED_PATH.match(path):
                target = pages_root() / SAVED_DIR / match.group(1)
                if target.is_file():
                    return self._file(target)
                return self._json(404, {"error": "not found"})
            if match := _PAGE_PATH.match(path):
                profile, slug, rest = match.groups()
                if rest is None:
                    return self._send(302, extra={"Location": f"{path}/"})
                target = _resolve_page_file(profile, slug, "index.html" if rest == "/" else rest)
                if target:
                    return self._file(target)
            self._json(404, {"error": "not found"})

        do_HEAD = do_GET

        def do_POST(self):
            """Answers arrive in the body, because only the viewer's browser holds them."""
            if not self._guard():
                return
            match = _PDF_PATH.match(urlsplit(self.path).path)
            if not match or match.group(1) == SAVED_DIR:
                return self._json(404, {"error": "not found"})
            length = int(self.headers.get("Content-Length") or 0)
            if length > _MAX_STATE_BYTES:
                return self._json(413, {"error": "too large"})
            try:
                state = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json(400, {"error": "bad json"})
            directory = pages_root() / match.group(1) / match.group(2)
            try:
                page = load_page_dir(directory)
                with tempfile.TemporaryDirectory(prefix="pagekit-pdf-") as folder:
                    target = render_pdf(page, Path(folder) / "page.pdf", state if isinstance(state, dict) else None)
                    data = target.read_bytes()
            except PageError as exc:
                missing = str(exc).startswith("no page at")
                return self._json(404 if missing else 500, {"error": str(exc)})
            disposition = f'attachment; filename="{match.group(2)}.pdf"'
            self._send(200, data, "application/pdf", {"Content-Disposition": disposition})

    return Handler


def start_pruner(interval: float = _PRUNE_INTERVAL_SECONDS) -> None:
    def loop() -> None:
        while True:
            try:
                prune_pages()
            except OSError:
                pass
            threading.Event().wait(interval)

    threading.Thread(target=loop, daemon=True, name="pagekit-pruner").start()


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler())
