"""Tests de bridge/portal_client.py: servir web/ desde el mismo puerto del
WebSocket (para que un solo túnel alcance, ver docs/remote-access.md) sin
abrir un agujero de path traversal -- este servidor puede quedar expuesto a
internet entero."""
from __future__ import annotations

import types
import unittest

from websockets.datastructures import Headers

from bridge.portal_client import WEB_ROOT, LocalPortalServer, _safe_static_path


def _request(path: str, upgrade: str = "") -> types.SimpleNamespace:
    headers = Headers()
    if upgrade:
        headers["Upgrade"] = upgrade
    return types.SimpleNamespace(path=path, headers=headers)


class TestSafeStaticPath(unittest.TestCase):
    def test_root_serves_index(self):
        self.assertEqual(_safe_static_path("/"), WEB_ROOT / "index.html")

    def test_existing_asset(self):
        self.assertEqual(_safe_static_path("/js/app.js"), WEB_ROOT / "js" / "app.js")

    def test_query_string_ignored(self):
        self.assertEqual(_safe_static_path("/?role=audience"), WEB_ROOT / "index.html")

    def test_nonexistent_file_rejected(self):
        self.assertIsNone(_safe_static_path("/no-existe.html"))

    def test_path_traversal_rejected(self):
        self.assertIsNone(_safe_static_path("/../CLAUDE.md"))
        self.assertIsNone(_safe_static_path("/../../bridge/config.py"))
        self.assertIsNone(_safe_static_path("/js/../../CLAUDE.md"))


class TestProcessRequest(unittest.IsolatedAsyncioTestCase):
    async def test_websocket_upgrade_passes_through(self):
        server = LocalPortalServer()
        result = await server._process_request(None, _request("/", upgrade="websocket"))
        self.assertIsNone(result)

    async def test_plain_http_serves_index(self):
        server = LocalPortalServer()
        response = await server._process_request(None, _request("/"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"ViruSynth", response.body)

    async def test_plain_http_404_for_traversal(self):
        server = LocalPortalServer()
        response = await server._process_request(None, _request("/../CLAUDE.md"))
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
