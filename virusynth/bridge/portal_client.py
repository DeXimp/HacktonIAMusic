"""Capa realtime de ViruSynth: adaptador de Portal + fallback 100% local.

`create_portal()` decide el backend:
  1. PortalSDKAdapter  — cuando exista SDK/credenciales reales (PORTAL_API_KEY).
  2. LocalPortalServer — servidor WebSocket local (ws://:8765), que ADEMÁS
     sirve la web estática (web/) desde el mismo puerto (ver
     `_process_request`) — así un solo túnel (ngrok o similar) alcanza para
     que alguien en OTRA red entre como audiencia/escenario y escuche el
     mini-sintetizador de web/js/audio-engine.js en tiempo real. Ver
     docs/remote-access.md. La demo NUNCA depende de un servicio externo
     (CLAUDE.md §7).
  3. NullPortal        — si falta `websockets`; el bridge sigue vivo sin web.

Protocolo JSON (mismos channels `jam:*` que usaría Portal):
  cliente→bridge: {"type":"hello","role":"audience|artist|stage","name":...}
                  {"type":"publish","channel":"jam:votes:cast","data":{...}}
  bridge→cliente: {"type":"state","channel":"jam:state","data":{...}}
"""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from . import config

log = logging.getLogger("PORTAL")

IncomingHandler = Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[None]]
_ROLES = {"audience", "artist", "stage"}

WEB_ROOT = (Path(__file__).resolve().parent.parent / "web").resolve()


def _safe_static_path(request_path: str) -> Optional[Path]:
    """Resuelve un path de request HTTP a un archivo dentro de web/, sin
    permitir escapar del directorio (path traversal) — este servidor puede
    quedar expuesto a internet entero vía un túnel, así que esto no es
    opcional."""
    clean = request_path.split("?", 1)[0].split("#", 1)[0]
    if clean in ("", "/"):
        clean = "/index.html"
    try:
        candidate = (WEB_ROOT / clean.lstrip("/")).resolve()
        candidate.relative_to(WEB_ROOT)
    except ValueError:
        return None
    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate if candidate.is_file() else None


class PortalBase:
    """Interfaz común. Cambiar de backend no toca el resto del bridge."""

    def set_handler(self, handler: IncomingHandler) -> None:
        self._handler = handler

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def publish(self, channel: str, data: dict[str, Any]) -> None: ...

    @property
    def presence(self) -> dict[str, int]:
        return {"performers": 0, "artists": 0, "audience": 0}


class NullPortal(PortalBase):
    async def publish(self, channel: str, data: dict[str, Any]) -> None:
        pass


class LocalPortalServer(PortalBase):
    """Fallback local: pub/sub + presence sobre websockets (dep. opcional)."""

    def __init__(self) -> None:
        self._handler: Optional[IncomingHandler] = None
        self._clients: dict[Any, dict[str, Any]] = {}
        self._server = None

    # ---- ciclo de vida -----------------------------------------------------
    async def start(self) -> None:
        import websockets  # import tardío: dependencia opcional

        self._server = await websockets.serve(
            self._on_connection, config.WS_HOST, config.WS_PORT,
            process_request=self._process_request,
            ping_interval=20, ping_timeout=20)
        log.info("Realtime local + web en http(s)/ws(s)://%s:%d "
                 "(fallback de Portal; un solo puerto para todo — ver docs/remote-access.md)",
                 config.WS_HOST, config.WS_PORT)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    # ---- web estática (mismo puerto que el WebSocket) ----------------------
    async def _process_request(self, connection: Any, request: Any) -> Any:
        """Deja pasar el handshake de WebSocket sin tocarlo; cualquier otra
        request HTTP (alguien abriendo la página en el navegador) la sirve
        directo desde web/ — así un solo túnel expone tanto la app como el
        realtime, sin necesitar un segundo `python -m http.server` ni un
        segundo link para compartir."""
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return None
        from websockets.http11 import Response
        from websockets.datastructures import Headers

        path = _safe_static_path(request.path)
        if path is None:
            body = b"404 not found"
            headers = Headers()
            headers["Content-Type"] = "text/plain; charset=utf-8"
            headers["Content-Length"] = str(len(body))
            return Response(404, "Not Found", headers, body)
        body = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        headers = Headers()
        headers["Content-Type"] = content_type
        headers["Content-Length"] = str(len(body))
        headers["Cache-Control"] = "no-cache"
        return Response(200, "OK", headers, body)

    # ---- conexiones --------------------------------------------------------
    async def _on_connection(self, ws) -> None:
        client = {"id": uuid.uuid4().hex[:8], "role": "audience", "name": ""}
        self._clients[ws] = client
        await self._notify_presence()
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await self._on_message(ws, client, msg)
        except Exception:
            pass
        finally:
            self._clients.pop(ws, None)
            if self._handler:
                await self._handler("client:gone", {"client_id": client["id"]}, client)
            await self._notify_presence()

    async def _on_message(self, ws, client: dict[str, Any],
                          msg: dict[str, Any]) -> None:
        mtype = msg.get("type")
        if mtype == "hello":
            role = msg.get("role")
            client["role"] = role if role in _ROLES else "audience"
            client["name"] = str(msg.get("name") or "")[:40]
            await self._send(ws, {"type": "welcome", "client_id": client["id"],
                                  "role": client["role"]})
            await self._notify_presence()
        elif mtype == "publish":
            channel = str(msg.get("channel") or "")
            data = msg.get("data")
            if channel.startswith("jam:") and isinstance(data, dict) and self._handler:
                await self._handler(channel, data, client)

    # ---- salida ------------------------------------------------------------
    async def _send(self, ws, payload: dict[str, Any]) -> None:
        try:
            await ws.send(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    async def publish(self, channel: str, data: dict[str, Any]) -> None:
        if not self._clients:
            return
        raw = json.dumps({"type": "state", "channel": channel, "data": data},
                         ensure_ascii=False)
        await asyncio.gather(*(self._safe_send(ws, raw)
                               for ws in list(self._clients)),
                             return_exceptions=True)

    async def _safe_send(self, ws, raw: str) -> None:
        try:
            await ws.send(raw)
        except Exception:
            self._clients.pop(ws, None)

    # ---- presence ----------------------------------------------------------
    @property
    def presence(self) -> dict[str, int]:
        counts = {"performers": 0, "artists": 0, "audience": 0}
        for c in self._clients.values():
            if c["role"] == "artist":
                counts["artists"] += 1
            elif c["role"] == "stage":
                counts["performers"] += 1   # la pantalla cuenta como escenario
            else:
                counts["audience"] += 1
        return counts

    async def _notify_presence(self) -> None:
        if self._handler:
            await self._handler("presence:changed", self.presence,
                                {"id": "server", "role": "system"})


class PortalSDKAdapter(PortalBase):
    """PUNTO DE INTEGRACIÓN con el SDK real de Portal.

    Cuando el hackathon entregue SDK/credenciales: implementar start/publish y
    mapear los mensajes entrantes a self._handler(channel, data, client) usando
    los MISMOS channels `jam:*` (docs/portal-channels.md). Nada más cambia.
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "Portal SDK aún sin integrar: implementa PortalSDKAdapter "
            "(ver docs/portal-channels.md) o deja PORTAL_API_KEY vacío "
            "para usar el fallback local.")


def create_portal() -> PortalBase:
    if config.PORTAL_API_KEY:
        try:
            return PortalSDKAdapter()
        except NotImplementedError as exc:
            log.warning("%s", exc)
    try:
        import websockets  # noqa: F401
        return LocalPortalServer()
    except ImportError:
        log.warning("'websockets' no instalado: bridge sin capa realtime")
        return NullPortal()
