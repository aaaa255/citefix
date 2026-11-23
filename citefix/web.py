"""Web app: python -m citefix serve [--host 127.0.0.1] [--port 8765]

GET  /             the page (citefix/web/)
GET  /api/example  the example passage
POST /api/review   {"text": ..., "repair": true} -> a stream of JSON lines, one event per line

For a public deployment, set CITEFIX_PER_IP_PER_HOUR and CITEFIX_DAILY_LIMIT (0 or unset means no limit)
and CITEFIX_TRUST_PROXY=1 when a proxy in front of the app sets X-Forwarded-For.
"""

from __future__ import annotations

import json
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import llm
from .review import review_passage

WEB_DIR = Path(__file__).resolve().parent / "web"
EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "passage.txt"
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
MAX_CHARS = 20_000
_running = threading.BoundedSemaphore(2)  # at most two checks at once
RECORD: Path | None = None  # dev option: save each check's events here
REPLAY: Path | None = None  # dev option: answer every check with these recorded events
PER_IP_PER_HOUR = int(os.environ.get("CITEFIX_PER_IP_PER_HOUR") or 0)
DAILY_LIMIT = int(os.environ.get("CITEFIX_DAILY_LIMIT") or 0)
TRUST_PROXY = os.environ.get("CITEFIX_TRUST_PROXY") == "1"


class _Quota:
    """Caps checks per visitor per hour and per day overall, so a public demo cannot run up the API bill."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_ip: dict[str, list[float]] = {}
        self._day = ""
        self._today = 0

    def take(self, ip: str) -> str | None:
        """Count one check for this address; return a message instead when a limit is reached."""
        now = time.time()
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        with self._lock:
            if day != self._day:
                self._day, self._today = day, 0
                self._by_ip.clear()
            recent = [t for t in self._by_ip.get(ip, []) if now - t < 3600]
            if DAILY_LIMIT and self._today >= DAILY_LIMIT:
                return ("This public demo has used up today's checks. It resets at midnight UTC; "
                        "you can also run citefix on your own computer.")
            if PER_IP_PER_HOUR and len(recent) >= PER_IP_PER_HOUR:
                checks = "check" if PER_IP_PER_HOUR == 1 else "checks"
                return f"This public demo allows {PER_IP_PER_HOUR} {checks} an hour from one address. Please try again later."
            recent.append(now)
            self._by_ip[ip] = recent
            self._today += 1
            return None


QUOTA = _Quota()


class Handler(BaseHTTPRequestHandler):
    server_version = "citefix"

    def do_HEAD(self) -> None:
        path = self.path.split("?", 1)[0]
        self.send_response(HTTPStatus.OK if path in STATIC else HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in STATIC:
            name, content_type = STATIC[path]
            self._send(HTTPStatus.OK, (WEB_DIR / name).read_bytes(), content_type)
        elif path == "/api/example":
            text = EXAMPLE.read_text(encoding="utf-8") if EXAMPLE.is_file() else ""
            self._send_json(HTTPStatus.OK, {"text": text})
        else:
            self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/review":
            return self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_CHARS * 4:
            return self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                                   {"message": f"The text is too long; paste at most {MAX_CHARS:,} characters."})
        try:
            request = json.loads(self.rfile.read(length) or b"{}")
            text = str(request.get("text") or "")
        except (ValueError, AttributeError):
            return self._send_json(HTTPStatus.BAD_REQUEST, {"message": "The request was not valid JSON."})
        if len(text) > MAX_CHARS:
            return self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                                   {"message": f"The text is too long; paste at most {MAX_CHARS:,} characters."})
        if not REPLAY:
            over = QUOTA.take(self._client_ip())
            if over:
                return self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"message": over})
        if not _running.acquire(blocking=False):
            return self._send_json(HTTPStatus.SERVICE_UNAVAILABLE,
                                   {"message": "Two checks are already running. Try again in a minute."})
        try:
            self._stream(text, bool(request.get("repair", True)))
        finally:
            _running.release()

    def _stream(self, text: str, repair: bool) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        lock, connected = threading.Lock(), [True]
        started = time.monotonic()
        recording = RECORD.open("w", encoding="utf-8") if RECORD else None

        def emit(kind: str, data: dict) -> None:
            event = {"type": kind, **data}
            line = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
            with lock:
                if recording:
                    recording.write(json.dumps({"t": round(time.monotonic() - started, 2), **event},
                                               ensure_ascii=False) + "\n")
                if not connected[0]:
                    return
                try:
                    self.wfile.write(line)
                    self.wfile.flush()
                except OSError:  # the browser went away; finish quietly
                    connected[0] = False

        try:
            if REPLAY:
                self._replay(emit)
            else:
                self._run_check(text, repair, emit, started)
        finally:
            if recording:
                recording.close()

    def _replay(self, emit) -> None:
        """Dev option: play back a recorded check at its original pace, clearly labelled."""
        emit("replay", {"text": f"Replaying a recorded check from {REPLAY.name}; nothing is being looked up live."})
        started = time.monotonic()
        for line in REPLAY.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            delay = event.pop("t", 0) - (time.monotonic() - started)
            if delay > 0:
                time.sleep(delay)
            emit(event.pop("type"), event)

    def _run_check(self, text: str, repair: bool, emit, started: float) -> None:
        before = (llm.usage.calls, llm.usage.prompt_tokens + llm.usage.completion_tokens)
        try:
            review_passage(text, repair=repair, emit=emit)
            emit("done", {"seconds": round(time.monotonic() - started, 1),
                          "calls": llm.usage.calls - before[0],
                          "tokens": llm.usage.prompt_tokens + llm.usage.completion_tokens - before[1]})
        except ValueError as err:
            emit("error", {"message": str(err)})
        except llm.LLMError as err:
            emit("error", {"message": f"The language model could not be used. {err}"})
        except Exception as err:  # keep the stream well-formed whatever happens
            emit("error", {"message": f"Something went wrong on the server: {err}"})

    def _client_ip(self) -> str:
        if TRUST_PROXY:
            forwarded = self.headers.get("X-Forwarded-For", "")
            if forwarded.strip():
                return forwarded.split(",")[0].strip()
        return self.client_address[0]

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, data: dict) -> None:
        self._send(status, json.dumps(data).encode("utf-8"), "application/json")

    def log_message(self, fmt: str, *args) -> None:  # one short line per request
        print(f"{self.command} {self.path.split('?', 1)[0]} {args[1] if len(args) > 1 else ''}", flush=True)


def serve(host: str = "127.0.0.1", port: int = 8765, record: str | None = None, replay: str | None = None) -> None:
    global RECORD, REPLAY
    RECORD = Path(record) if record else None
    REPLAY = Path(replay) if replay else None
    if REPLAY and not REPLAY.is_file():
        raise SystemExit(f"No recording at {REPLAY}")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"citefix is running at http://{'localhost' if host == '127.0.0.1' else host}:{port}  (Ctrl+C stops it)",
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
