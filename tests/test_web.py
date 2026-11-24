"""Serving the page: the React build when there is one, else the classic page; nothing outside the page folder."""

import contextlib
import http.client
import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from citefix import web


class PageServingTest(unittest.TestCase):
    """The real request handler on a free local port, with a stand-in build folder."""

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
        self.root = Path(folder.name)
        self.build = self.root / "dist"
        (self.build / "assets").mkdir(parents=True)
        (self.root / "secret.txt").write_text("not for the web", encoding="utf-8")
        patcher = mock.patch.object(web, "BUILD_DIR", self.build)
        patcher.start()
        self.addCleanup(patcher.stop)
        log = contextlib.redirect_stdout(io.StringIO())
        log.__enter__()
        self.addCleanup(log.__exit__, None, None, None)

    def build_page(self):
        (self.build / "index.html").write_text("<!doctype html><title>react build</title>", encoding="utf-8")
        (self.build / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
        (self.build / "assets" / "font.woff2").write_bytes(b"wOF2")
        (self.build / "assets" / "notes.md").write_text("# not a page file", encoding="utf-8")

    def get(self, path, method="GET"):
        """Sends the path exactly as written, without any client-side clean-up of dots."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.putrequest(method, path, skip_accept_encoding=True)
            connection.endheaders()
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_without_a_build_the_classic_page_is_served(self):
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertEqual(body, (web.WEB_DIR / "index.html").read_bytes())
        self.assertEqual(self.get("/app.js")[0], 200)
        self.assertEqual(self.get("/style.css")[1]["Content-Type"], "text/css; charset=utf-8")

    def test_the_build_is_served_once_it_exists(self):
        self.build_page()
        status, headers, body = self.get("/")
        self.assertEqual((status, body), (200, b"<!doctype html><title>react build</title>"))
        self.assertEqual(headers["Cache-Control"], "no-cache")
        self.assertIn("font-src 'self'", headers["Content-Security-Policy"])
        status, headers, _ = self.get("/assets/index-abc123.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/javascript; charset=utf-8")
        self.assertIn("immutable", headers["Cache-Control"])
        self.assertEqual(self.get("/assets/font.woff2")[1]["Content-Type"], "font/woff2")
        self.assertEqual(self.get("/app.js")[0], 404)  # the classic files are not mixed in

    def test_nothing_outside_the_page_folder_or_of_another_type(self):
        self.build_page()
        for path in ("/../secret.txt", "/assets/../../secret.txt", "/%2e%2e/secret.txt", "/assets/notes.md",
                     "/assets/", "/missing.js", "/.", "//etc/passwd"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path)[0], 404)

    def test_head_matches_get(self):
        self.build_page()
        self.assertEqual(self.get("/", method="HEAD")[0], 200)
        self.assertEqual(self.get("/missing.js", method="HEAD")[0], 404)

    def test_the_api_still_answers(self):
        self.build_page()
        status, headers, _ = self.get("/api/example")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json")


if __name__ == "__main__":
    unittest.main()
