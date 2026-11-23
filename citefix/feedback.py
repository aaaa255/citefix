"""Feedback from testers: a right/wrong mark on each note, a rating and a comment, one JSON record per send.

Each record is printed to the server log, written under FEEDBACK_DIR (default ./feedback) and, when
FEEDBACK_REPO ("owner/name") and FEEDBACK_GITHUB_TOKEN are set, committed to that private GitHub
repository. A free host wipes its disk whenever the instance sleeps, so the repository is the copy that lasts.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.request
import uuid
from pathlib import Path

MAX_BYTES = 200_000
MAX_CITATIONS = 60
VOTES = ("right", "wrong")
LOCAL_DIR = Path(os.environ.get("FEEDBACK_DIR") or Path(__file__).resolve().parents[1] / "feedback")


class FeedbackError(ValueError):
    """The submission was empty or could not be read."""


def _text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _int(value, low: int, high: int) -> int | None:
    ok = isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
    return value if ok else None


def _seconds(value) -> float | None:
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value < 86_400
    return round(float(value), 1) if ok else None


def clean(payload) -> dict:
    """Keep only the expected fields, with bounded sizes, and stamp the record."""
    if not isinstance(payload, dict):
        raise FeedbackError("The feedback could not be read.")
    citations = []
    for item in payload.get("citations") or []:
        if not isinstance(item, dict) or len(citations) >= MAX_CITATIONS:
            continue
        citations.append({
            "ref": _int(item.get("ref"), 1, 10_000),
            "claim": _text(item.get("claim"), 600),
            "reference": _text(item.get("reference"), 600),
            "existence": _text(item.get("existence"), 30),
            "verdict": _text(item.get("verdict"), 40),
            "quote": _text(item.get("quote"), 800),
            "fix": _text(item.get("fix"), 30),
            "suggested": _text(item.get("suggested"), 600),
            "vote": item.get("vote") if item.get("vote") in VOTES else None,
            "why": _text(item.get("why"), 300),
        })
    record = {
        "id": uuid.uuid4().hex[:12],
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": (os.environ.get("RENDER_GIT_COMMIT") or "local")[:12],
        "check": _text(payload.get("check"), 40),  # the same check sent again replaces the earlier send
        "replay": payload.get("replay") is True,
        "tester": _text(payload.get("tester"), 60),
        "rating": _int(payload.get("rating"), 1, 5),
        "comment": _text(payload.get("comment"), 4000),
        "seconds": _seconds(payload.get("seconds")),
        "citations": citations,
    }
    if not any(c["vote"] for c in citations) and record["rating"] is None and not record["comment"]:
        raise FeedbackError("Mark a note right or wrong, choose a rating or write a comment first.")
    return record


def relative_path(record: dict) -> str:
    """Where a record is stored: <date>/<time>-<id>.json, so a folder listing reads in order."""
    return f"{record['time'][:10]}/{record['time'][11:19].replace(':', '')}-{record['id']}.json"


def _to_github(record: dict, body: str) -> bool:
    repo, token = os.environ.get("FEEDBACK_REPO"), os.environ.get("FEEDBACK_GITHUB_TOKEN")
    if not repo or not token:
        return False
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/contents/feedback/{relative_path(record)}",
        data=json.dumps({"message": f"Feedback {record['id']}",
                         "content": base64.b64encode(body.encode("utf-8")).decode("ascii")}).encode("utf-8"),
        method="PUT",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "User-Agent": "citefix-feedback", "X-GitHub-Api-Version": "2022-11-28"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15):
            return True
    except Exception as err:  # best effort: the log and the local file still have the record
        print(f"FEEDBACK_GITHUB_ERROR {getattr(err, 'code', '')} {err}", flush=True)
        return False


def save(record: dict) -> list[str]:
    """Save one record; returns where it went ("log", "file", "github")."""
    body = json.dumps(record, ensure_ascii=False, indent=2)
    print("FEEDBACK " + json.dumps(record, ensure_ascii=False), flush=True)
    places = ["log"]
    try:
        path = LOCAL_DIR / relative_path(record)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        places.append("file")
    except OSError as err:
        print(f"FEEDBACK_FILE_ERROR {err}", flush=True)
    if _to_github(record, body):
        places.append("github")
    return places
