"""Tester feedback and the web endpoints, offline: no model, no scholarly APIs, no GitHub."""

import base64
import contextlib
import http.client
import io
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from citefix import feedback, web

NO_GITHUB = {"FEEDBACK_REPO": "", "FEEDBACK_GITHUB_TOKEN": ""}


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


class CleanTest(unittest.TestCase):
    def test_keeps_known_fields_within_bounds(self):
        record = feedback.clean({
            "check": "abc", "rating": 4, "comment": "x" * 5000, "tester": "  Li ", "extra": "dropped",
            "seconds": 21.37, "replay": "yes",
            "citations": [
                {"ref": 3, "claim": "c", "vote": "wrong", "why": "it does say so", "verdict": "not_supported",
                 "unknown": 1},
                {"ref": True, "vote": "maybe"},
                "not a note",
            ],
        })
        self.assertEqual(len(record["id"]), 12)
        self.assertEqual((record["check"], record["rating"], record["tester"]), ("abc", 4, "Li"))
        self.assertEqual(len(record["comment"]), 4000)
        self.assertEqual(record["seconds"], 21.4)
        self.assertFalse(record["replay"])  # only a real true counts
        self.assertNotIn("extra", record)
        first, second = record["citations"]
        self.assertEqual((first["ref"], first["vote"], first["why"]), (3, "wrong", "it does say so"))
        self.assertNotIn("unknown", first)
        self.assertEqual((second["ref"], second["vote"]), (None, None))

    def test_keeps_a_reason_long_enough_for_a_link(self):
        record = feedback.clean({"citations": [{"ref": 1, "vote": "wrong", "why": "y" * 1200}]})
        self.assertEqual(len(record["citations"][0]["why"]), 1000)

    def test_drops_numbers_out_of_range(self):
        record = feedback.clean({"rating": 9, "seconds": -1, "comment": "ok"})
        self.assertIsNone(record["rating"])
        self.assertIsNone(record["seconds"])
        self.assertIsNone(feedback.clean({"rating": True, "comment": "ok"})["rating"])

    def test_refuses_an_empty_send(self):
        for payload in ({}, {"citations": [{"ref": 1}]}, {"comment": "   "}, [], "text"):
            with self.subTest(payload=payload), self.assertRaises(feedback.FeedbackError):
                feedback.clean(payload)


class SaveTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        patcher = mock.patch.object(feedback, "LOCAL_DIR", self.folder)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.record = feedback.clean({"comment": "useful", "rating": 5})

    def test_writes_one_file_and_skips_github_without_settings(self):
        with mock.patch.dict(os.environ, NO_GITHUB), quiet() as log:
            places = feedback.save(self.record)
        self.assertEqual(places, ["log", "file"])
        saved = self.folder / feedback.relative_path(self.record)
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8"))["comment"], "useful")
        self.assertIn(f'"id": "{self.record["id"]}"', log.getvalue())

    def test_commits_to_github_when_configured(self):
        sent = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(request, timeout):
            sent.append(request)
            return Response()

        settings = {"FEEDBACK_REPO": "owner/feedback", "FEEDBACK_GITHUB_TOKEN": "test-token"}
        with mock.patch.dict(os.environ, settings), \
                mock.patch.object(feedback.urllib.request, "urlopen", fake_urlopen), quiet():
            places = feedback.save(self.record)
        self.assertEqual(places, ["log", "file", "github"])
        request = sent[0]
        self.assertEqual(request.get_method(), "PUT")
        self.assertEqual(request.full_url, "https://api.github.com/repos/owner/feedback/contents/feedback/"
                                           + feedback.relative_path(self.record))
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        content = json.loads(base64.b64decode(json.loads(request.data)["content"]))
        self.assertEqual(content["id"], self.record["id"])

    def test_a_github_failure_keeps_the_other_copies(self):
        def offline(request, timeout):
            raise urllib.error.URLError("offline")

        settings = {"FEEDBACK_REPO": "owner/feedback", "FEEDBACK_GITHUB_TOKEN": "test-token"}
        with mock.patch.dict(os.environ, settings), \
                mock.patch.object(feedback.urllib.request, "urlopen", offline), quiet() as log:
            places = feedback.save(self.record)
        self.assertEqual(places, ["log", "file"])
        self.assertIn("FEEDBACK_GITHUB_ERROR", log.getvalue())


class QuotaTest(unittest.TestCase):
    def test_limits_each_address_per_hour(self):
        quota = web._Quota(2, 0, ("check", "checks"))
        self.assertIsNone(quota.take("a"))
        self.assertIsNone(quota.take("a"))
        self.assertIn("2 checks an hour", quota.take("a"))
        self.assertIsNone(quota.take("b"))
        single = web._Quota(1, 0, ("check", "checks"))
        single.take("a")
        self.assertIn("1 check an hour", single.take("a"))

    def test_daily_limit_covers_everyone(self):
        quota = web._Quota(0, 1, ("feedback submission", "feedback submissions"))
        self.assertIsNone(quota.take("a"))
        self.assertIn("today's feedback submissions", quota.take("b"))


class ServerTest(unittest.TestCase):
    """The real request handler on a free local port."""

    @classmethod
    def setUpClass(cls):
        cls.server = web.ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        for patcher in (mock.patch.object(feedback, "LOCAL_DIR", self.folder),
                        mock.patch.object(web, "FEEDBACK_QUOTA", web._Quota(0, 0, ("send", "sends"))),
                        mock.patch.dict(os.environ, NO_GITHUB)):
            patcher.start()
            self.addCleanup(patcher.stop)
        log = quiet()
        log.__enter__()
        self.addCleanup(log.__exit__, None, None, None)

    def post(self, path, body):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=body, method="POST",
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as err:
            return err.code, err.read()

    def test_feedback_is_saved(self):
        status, body = self.post("/api/feedback", json.dumps({"rating": 4, "comment": "fine"}).encode())
        self.assertEqual(status, 200)
        answer = json.loads(body)
        self.assertEqual(answer["saved"], ["log", "file"])
        self.assertEqual(len(list(self.folder.rglob("*.json"))), 1)

    def test_unusable_feedback_is_refused(self):
        self.assertEqual(self.post("/api/feedback", b"{}")[0], 400)
        self.assertEqual(self.post("/api/feedback", b"not json")[0], 400)
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:  # announce a body that is too long; the server answers without reading it
            connection.putrequest("POST", "/api/feedback")
            connection.putheader("Content-Length", str(feedback.MAX_BYTES + 1))
            connection.endheaders()
            self.assertEqual(connection.getresponse().status, 413)
        finally:
            connection.close()
        self.assertEqual(list(self.folder.rglob("*.json")), [])

    def replay_with_slots_taken(self, **settings):
        """Run a replayed check while both check slots are held; returns (stream, release_one)."""
        recording = self.folder / "run.ndjson"
        recording.write_text('{"t": 0, "type": "done", "seconds": 0, "calls": 0, "tokens": 0}\n', encoding="utf-8")
        for name, value in {"REPLAY": recording, **settings}.items():
            patcher = mock.patch.object(web, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        held = [0]
        for _ in range(2):
            web._running.acquire()
            held[0] += 1

        def release_one():
            web._running.release()
            held[0] -= 1

        self.addCleanup(lambda: [web._running.release() for _ in range(held[0])])
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/review", data=b'{"text": "x"}',
                                         method="POST")
        return urllib.request.urlopen(request, timeout=10), release_one

    def test_a_check_waits_for_a_free_slot(self):
        stream, release_one = self.replay_with_slots_taken(WAIT_POLL_S=0.05)
        with stream:
            self.assertEqual(json.loads(stream.readline())["type"], "queued")
            release_one()  # one of the running checks finishes
            types = [json.loads(line)["type"] for line in stream.read().splitlines() if line.strip()]
        self.assertEqual(types[-2:], ["replay", "done"])
        self.assertEqual(set(types[:-2]) - {"queued"}, set())

    def test_a_check_gives_up_when_no_slot_frees(self):
        stream, _ = self.replay_with_slots_taken(WAIT_POLL_S=0.05, MAX_WAIT_S=0.2)
        with stream:
            events = [json.loads(line) for line in stream.read().splitlines() if line.strip()]
        self.assertEqual(events[0]["type"], "queued")
        self.assertEqual(events[-1]["type"], "error")
        self.assertIn("busy", events[-1]["message"])


if __name__ == "__main__":
    unittest.main()
