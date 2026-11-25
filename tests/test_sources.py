"""Offline tests of the in-memory cache of lookups (no network)."""

import io
import unittest
import urllib.error
from unittest import mock

from citefix import sources

URL = "https://api.example.org/works?search=attention"


class Reply(io.BytesIO):
    """Stands in for an HTTP response."""
    headers: dict = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(URL, code, "error", {}, None)


class CacheTest(unittest.TestCase):
    def setUp(self):
        sources._cache.clear()

    def test_a_repeated_lookup_is_answered_from_memory(self):
        with mock.patch("urllib.request.urlopen", side_effect=lambda *a, **k: Reply(b'{"ok": 1}')) as net:
            first = sources._get(URL, "openalex")
            second = sources._get(URL, "openalex")
        self.assertEqual((first, second), (b'{"ok": 1}', b'{"ok": 1}'))
        self.assertEqual(net.call_count, 1)

    def test_no_such_record_is_remembered_too(self):
        with mock.patch("urllib.request.urlopen", side_effect=error(404)) as net:
            self.assertIsNone(sources._get(URL, "openalex"))
            self.assertIsNone(sources._get(URL, "openalex"))
        self.assertEqual(net.call_count, 1)

    def test_errors_are_not_remembered(self):
        with mock.patch("urllib.request.urlopen", side_effect=[error(400), Reply(b"{}")]) as net:
            with self.assertRaises(sources.SourceError):
                sources._get(URL, "openalex")
            self.assertEqual(sources._get(URL, "openalex"), b"{}")
        self.assertEqual(net.call_count, 2)

    def test_turned_off(self):
        with mock.patch.object(sources, "_CACHE_HOURS", 0), \
                mock.patch("urllib.request.urlopen", side_effect=lambda *a, **k: Reply(b"{}")) as net:
            sources._get(URL, "openalex")
            sources._get(URL, "openalex")
        self.assertEqual(net.call_count, 2)

    def test_old_replies_are_dropped(self):
        with mock.patch("urllib.request.urlopen", side_effect=lambda *a, **k: Reply(b"{}")) as net:
            sources._get(URL, "openalex")
            stored, body = sources._cache[URL]
            sources._cache[URL] = (stored - sources._CACHE_HOURS * 3600 - 1, body)
            sources._get(URL, "openalex")
        self.assertEqual(net.call_count, 2)


if __name__ == "__main__":
    unittest.main()
