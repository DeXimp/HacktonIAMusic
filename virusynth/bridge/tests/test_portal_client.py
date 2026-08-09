"""Tests de bridge/portal_client.py: servir web/ desde el mismo puerto del
WebSocket (para que un solo túnel alcance, ver docs/remote-access.md) sin
abrir un agujero de path traversal -- este servidor puede quedar expuesto a
internet entero. Y el adaptador de Portal (useportal.co): mapeo de frames del
wire protocol v1 -> channels `jam:*`, sin tocar la red.

Los frames de Portal que se usan acá estan copiados de una sesion real contra
wss://realtime.useportal.co, no inventados."""
from __future__ import annotations

import base64
import json
import time
import types
import unittest

from websockets.datastructures import Headers

from bridge import config
from bridge.portal_client import (WEB_ROOT, CompositePortal, LocalPortalServer,
                                  NullPortal, PortalSDKAdapter, _jwt_exp,
                                  _safe_static_path, create_portal)


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

    async def test_portal_config_endpoint(self):
        server = LocalPortalServer()
        response = await server._process_request(None, _request("/portal-config.json"))
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload["room"], config.PORTAL_ROOM)
        self.assertIn("realtime.useportal.co", payload["realtimeUrl"])


class _FakeWS:
    """Captura lo que el adaptador manda al socket."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))


def _adapter() -> PortalSDKAdapter:
    original, config.PORTAL_API_KEY = config.PORTAL_API_KEY, "pk_test"
    try:
        return PortalSDKAdapter()
    finally:
        config.PORTAL_API_KEY = original


class TestPortalAdapterFrames(unittest.IsolatedAsyncioTestCase):
    """`ready`/`presence`/`ephemeral` tal como los manda Portal de verdad."""

    def setUp(self) -> None:
        self.adapter = _adapter()
        self.seen: list[tuple[str, dict, dict]] = []

        async def handler(channel, data, client):
            self.seen.append((channel, data, client))

        self.adapter.set_handler(handler)

    async def test_ready_snapshot_counts_roles_and_skips_bridge(self):
        await self.adapter._on_frame({
            "t": "ready", "seq": 0, "leaf": "leaf_0",
            "presence": {"mode": "detailed", "count": 4, "participants": [
                {"id": "anon_a", "anon": True, "metadata": {"role": "audience"}},
                {"id": "anon_b", "anon": True, "metadata": {"role": "artist"}},
                {"id": "anon_c", "anon": True, "metadata": {"role": "stage"}},
                {"id": "anon_me", "anon": True, "metadata": {"role": "bridge"}}]}})
        self.assertEqual(self.adapter.presence,
                         {"performers": 1, "artists": 1, "audience": 1})
        self.assertEqual(self.seen[-1][0], "presence:changed")

    async def test_join_and_leave_emit_client_gone(self):
        await self.adapter._on_frame({
            "t": "presence", "mode": "detailed", "count": 1,
            "joined": [{"id": "anon_x", "metadata": {"role": "artist"}}], "left": []})
        self.assertEqual(self.adapter.presence["artists"], 1)

        await self.adapter._on_frame({
            "t": "presence", "mode": "detailed", "count": 0,
            "joined": [], "left": [{"id": "anon_x"}]})
        self.assertEqual(self.adapter.presence["artists"], 0)
        self.assertIn(("client:gone", {"client_id": "anon_x"}),
                      [(c, d) for c, d, _ in self.seen])

    async def test_aggregate_presence_discounts_the_bridge(self):
        await self.adapter._on_frame({"t": "ready", "presence": {
            "mode": "aggregate", "count": 51, "recent": []}})
        self.assertEqual(self.adapter.presence["audience"], 50)

    async def test_ephemeral_becomes_jam_channel(self):
        await self.adapter._on_frame({
            "t": "presence", "mode": "detailed", "count": 1,
            "joined": [{"id": "anon_v", "metadata": {"role": "artist"}}], "left": []})
        await self.adapter._on_frame({
            "t": "ephemeral", "userId": "anon_v", "type": "jam:votes:cast",
            "content": {"bpm": 128}})
        channel, data, client = self.seen[-1]
        self.assertEqual(channel, "jam:votes:cast")
        self.assertEqual(data, {"bpm": 128})
        self.assertEqual((client["id"], client["role"]), ("anon_v", "artist"))

    async def test_non_jam_channel_ignored(self):
        await self.adapter._on_frame({"t": "ephemeral", "userId": "x",
                                      "type": "otra:cosa", "content": {"a": 1}})
        self.assertEqual(self.seen, [])


class TestPortalAdapterPublish(unittest.IsolatedAsyncioTestCase):
    async def test_publish_sends_ephemeral_frame(self):
        adapter = _adapter()
        adapter._ws = _FakeWS()
        await adapter.publish("jam:note_triggered", {"note": 60, "velocity": 100})
        frame = adapter._ws.sent[0]
        self.assertEqual(frame["t"], "ephemeral")          # nunca persistente
        self.assertEqual(frame["type"], "jam:note_triggered")
        self.assertEqual(frame["content"], {"note": 60, "velocity": 100})
        self.assertTrue(frame["cl"])

    async def test_oversized_payload_dropped_not_sent(self):
        adapter = _adapter()
        adapter._ws = _FakeWS()
        await adapter.publish("jam:state", {"blob": "x" * 3000})
        self.assertEqual(adapter._ws.sent, [])

    async def test_publish_without_connection_is_a_noop(self):
        adapter = _adapter()
        await adapter.publish("jam:state", {"bpm": 120})   # no debe explotar


class TestCompositePortal(unittest.IsolatedAsyncioTestCase):
    class _Backend(NullPortal):
        def __init__(self, counts):
            self._counts = counts
            self.published = []

        async def publish(self, channel, data):
            self.published.append((channel, data))

        @property
        def presence(self):
            return self._counts

    async def test_publishes_to_every_backend(self):
        a = self._Backend({"performers": 0, "artists": 0, "audience": 0})
        b = self._Backend({"performers": 0, "artists": 0, "audience": 0})
        composite = CompositePortal([a, b])
        await composite.publish("jam:state", {"bpm": 120})
        self.assertEqual(a.published, [("jam:state", {"bpm": 120})])
        self.assertEqual(b.published, [("jam:state", {"bpm": 120})])

    async def test_presence_is_the_sum_not_the_last_writer(self):
        composite = CompositePortal([
            self._Backend({"performers": 1, "artists": 0, "audience": 3}),
            self._Backend({"performers": 0, "artists": 2, "audience": 5})])
        self.assertEqual(composite.presence,
                         {"performers": 1, "artists": 2, "audience": 8})

    async def test_presence_changed_is_recomputed_from_all_backends(self):
        local = self._Backend({"performers": 0, "artists": 0, "audience": 2})
        remote = self._Backend({"performers": 0, "artists": 0, "audience": 7})
        composite = CompositePortal([local, remote])
        seen = []

        async def handler(channel, data, client):
            seen.append((channel, data))

        composite.set_handler(handler)
        # un backend avisa con SU cuenta; el composite debe reportar el total
        await composite._relay("presence:changed", local.presence,
                               {"id": "x", "role": "system"})
        self.assertEqual(seen[-1][1]["audience"], 9)


class TestCreatePortal(unittest.TestCase):
    def test_without_key_only_local(self):
        original, config.PORTAL_API_KEY = config.PORTAL_API_KEY, ""
        try:
            self.assertIsInstance(create_portal(), LocalPortalServer)
        finally:
            config.PORTAL_API_KEY = original

    def test_with_key_local_stays_as_fallback(self):
        original, config.PORTAL_API_KEY = config.PORTAL_API_KEY, "pk_test"
        try:
            portal = create_portal()
            self.assertIsInstance(portal, CompositePortal)
            kinds = [type(b) for b in portal._backends]
            self.assertIn(LocalPortalServer, kinds)   # CLAUDE.md §7
            self.assertIn(PortalSDKAdapter, kinds)
        finally:
            config.PORTAL_API_KEY = original


class TestJwtExp(unittest.TestCase):
    def test_reads_exp(self):
        exp = int(time.time()) + 3600
        body = base64.urlsafe_b64encode(
            json.dumps({"sub": "anon_x", "exp": exp}).encode()).decode().rstrip("=")
        self.assertEqual(_jwt_exp(f"aaa.{body}.bbb"), float(exp))

    def test_garbage_is_zero_not_an_exception(self):
        self.assertEqual(_jwt_exp("no-es-un-jwt"), 0.0)


if __name__ == "__main__":
    unittest.main()
