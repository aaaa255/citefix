"""Web app: python -m citefix serve [--host 127.0.0.1] [--port 8765]

GET  /             the page: the React build in frontend/dist (cd frontend && npm install && npm run build),
                   or the classic page in citefix/web/ when there is no build
GET  /api/example  the example passage
POST /api/review   {"text": ..., "repair": true} -> a stream of JSON lines, one event per line
POST /api/feedback a tester's votes and comments on one check (see feedback.py)

For a public deployment, set CITEFIX_PER_IP_PER_HOUR and CITEFIX_DAILY_LIMIT (0 or unset means no limit)
and CITEFIX_TRUST_PROXY=1 when a proxy in front of the app sets X-Forwarded-For.
At most two checks run at once; a third waits for a free slot (sending "queued" events) for up to MAX_WAIT_S.
"""

from __future__ import annotations

import json
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import feedback, llm
from .review import review_passage

WEB_DIR = Path(__file__).resolve().parent / "web"  # the classic page: plain HTML, CSS and JavaScript
BUILD_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"  # the React page, once it is built
EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "passage.txt"
TYPES = {  # the only kinds of file the page folder may serve
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
}
# Fonts come from the page's own folder (React build) or Google Fonts (classic page).
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
MAX_CHARS = 20_000
_running = threading.BoundedSemaphore(2)  # at most two checks at once
MAX_WAIT_S = 180  # how long a check waits for a free slot before giving up
WAIT_POLL_S = 10.0  # how often a waiting check tells the browser it is still waiting
RECORD: Path | None = None  # dev option: save each check's events here
REPLAY: Path | None = None  # dev option: answer every check with these recorded events
PER_IP_PER_HOUR = int(os.environ.get("CITEFIX_PER_IP_PER_HOUR") or 0)
DAILY_LIMIT = int(os.environ.get("CITEFIX_DAILY_LIMIT") or 0)
TRUST_PROXY = os.environ.get("CITEFIX_TRUST_PROXY") == "1"


class _Quota:
    """Caps requests per visitor per hour and per day overall, so a public demo cannot run up the API bill."""

    def __init__(self, per_ip_per_hour: int, daily: int, noun: tuple[str, str]) -> None:
        self.per_ip_per_hour, self.daily, self.noun = per_ip_per_hour, daily, noun  # noun: (singular, plural)
        self._lock = threading.Lock()
        self._by_ip: dict[str, list[float]] = {}
        self._day = ""
        self._today = 0

    def take(self, ip: str) -> str | None:
        """Count one request for this address; return a message instead when a limit is reached."""
        now = time.time()
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        with self._lock:
            if day != self._day:
                self._day, self._today = day, 0
                self._by_ip.clear()
            recent = [t for t in self._by_ip.get(ip, []) if now - t < 3600]
            if self.daily and self._today >= self.daily:
                return (f"This public demo has used up today's {self.noun[1]}. It resets at midnight UTC; "
                        "you can also run citefix on your own computer.")
            if self.per_ip_per_hour and len(recent) >= self.per_ip_per_hour:
                what = self.noun[0] if self.per_ip_per_hour == 1 else self.noun[1]
                return (f"This public demo allows {self.per_ip_per_hour} {what} an hour from one address. "
                        "Please try again later.")
            recent.append(now)
            self._by_ip[ip] = recent
            self._today += 1
            return None


def page_dir() -> Path:
    """The folder the page is served from: the React build when there is one, else the classic page."""
    return BUILD_DIR if (BUILD_DIR / "index.html").is_file() else WEB_DIR


def static_file(path: str) -> Path | None:
    """The file a GET path names in the page folder: a known type, inside the folder, or None."""
    root = page_dir().resolve()
    name = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
    try:
        file = (root / name).resolve()
        if file.suffix.lower() in TYPES and file.is_relative_to(root) and file.is_file():
            return file
    except (OSError, ValueError):  # a name the file system cannot even look up
        pass
    return None


QUOTA = _Quota(PER_IP_PER_HOUR, DAILY_LIMIT, ("check", "checks"))
# Generous per address because a class on one campus network shares an IP; 500 a day stays inside
# GitHub's limit on commits made through its API.
FEEDBACK_QUOTA = _Quota(120, 500, ("feedback submission", "feedback submissions"))


class Handler(BaseHTTPRequestHandler):
    server_version = "citefix"

    def do_HEAD(self) -> None:
        path = self.path.split("?", 1)[0]
        self.send_response(HTTPStatus.OK if static_file(path) else HTTPStatus.NOT_FOUND)
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/example":
            text = EXAMPLE.read_text(encoding="utf-8") if EXAMPLE.is_file() else ""
            return self._send_json(HTTPStatus.OK, {"text": text})
        file = static_file(path)
        if not file:
            return self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")
        # The build's /assets/ files carry a content hash in their names, so a browser may keep them for good.
        cache = "public, max-age=31536000, immutable" if path.startswith("/assets/") else "no-cache"
        self._send(HTTPStatus.OK, file.read_bytes(), TYPES[file.suffix.lower()], cache)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/feedback":
            return self._feedback()
        if path != "/api/review":
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
        self._stream(text, bool(request.get("repair", True)))

    def _stream(self, text: str, repair: bool) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        lock, connected = threading.Lock(), [True]
        recording, started = None, time.monotonic()

        def emit(kind: str, data: dict) -> bool:
            """Send one event; returns False once the browser has gone away."""
            event = {"type": kind, **data}
            line = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
            with lock:
                if recording:
                    recording.write(json.dumps({"t": round(time.monotonic() - started, 2), **event},
                                               ensure_ascii=False) + "\n")
                if connected[0]:
                    try:
                        self.wfile.write(line)
                        self.wfile.flush()
                    except OSError:  # the browser went away; finish quietly
                        connected[0] = False
                return connected[0]

        if not self._wait_for_slot(emit):
            return
        try:
            started = time.monotonic()  # a recording starts when the check does, not when it began to wait
            recording = RECORD.open("w", encoding="utf-8") if RECORD else None
            if REPLAY:
                self._replay(emit)
            else:
                self._run_check(text, repair, emit, started)
        finally:
            _running.release()
            if recording:
                recording.close()

    def _wait_for_slot(self, emit) -> bool:
        """Take one of the check slots, telling the browser while it waits; False if it gave up."""
        if _running.acquire(blocking=False):
            return True
        waited = 0.0
        while waited < MAX_WAIT_S:
            if not emit("queued", {"text": "Two other checks are running. Yours starts as soon as one finishes."}):
                return False  # nobody is waiting for this one any more
            if _running.acquire(timeout=WAIT_POLL_S):
                return True
            waited += WAIT_POLL_S
        emit("error", {"message": "citefix is busy right now. Please try again in a few minutes."})
        return False

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

    def _feedback(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0:
            return self._send_json(HTTPStatus.BAD_REQUEST, {"message": "The feedback could not be read."})
        if length > feedback.MAX_BYTES:
            return self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"message": "The feedback is too long."})
        over = FEEDBACK_QUOTA.take(self._client_ip())
        if over:
            return self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"message": over})
        try:
            record = feedback.clean(json.loads(self.rfile.read(length) or b"{}"))
        except feedback.FeedbackError as err:
            return self._send_json(HTTPStatus.BAD_REQUEST, {"message": str(err)})
        except ValueError:
            return self._send_json(HTTPStatus.BAD_REQUEST, {"message": "The feedback could not be read."})
        self._send_json(HTTPStatus.OK, {"id": record["id"], "saved": feedback.save(record)})

    def _client_ip(self) -> str:
        if TRUST_PROXY:
            forwarded = self.headers.get("X-Forwarded-For", "")
            if forwarded.strip():
                return forwarded.split(",")[0].strip()
        return self.client_address[0]

    def _send(self, status: HTTPStatus, body: bytes, content_type: str, cache: str = "no-cache") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", cache)
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
    if page_dir() == BUILD_DIR:
        print("Page: the React build in frontend/dist", flush=True)
    else:
        print("Page: the classic page in citefix/web (for the new one: cd frontend && npm install && npm run build)",
              flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
