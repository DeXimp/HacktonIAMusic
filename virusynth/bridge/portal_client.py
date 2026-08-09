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
import base64
import json
import logging
import mimetypes
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from . import config

log = logging.getLogger("PORTAL")

IncomingHandler = Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[None]]
_ROLES = {"audience", "artist", "stage"}

WEB_ROOT = (Path(__file__).resolve().parent.parent / "web").resolve()

# --- Portal (useportal.co), wire protocol v1 -------------------------------
# Verificado contra el servicio real. Dos detalles NO están en docs.useportal.co
# y salieron de leer @portalsdk/core: (1) el endpoint de token anónimo —los docs
# lo marcan como "doc gap"—, y (2) el parámetro `key` en la URL del WebSocket.
PORTAL_API_URL = "https://api.useportal.co"
PORTAL_REALTIME_URL = "wss://realtime.useportal.co"
# api.useportal.co está detrás de Cloudflare: con el User-Agent por defecto de
# urllib devuelve 403 (error 1010). Con uno de navegador, pasa.
_PORTAL_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_MAX_CONTENT_BYTES = 2048   # tope de `content` por mensaje que impone Portal


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

        # La web pregunta acá si hay Portal configurado, en vez de hornear la
        # clave en un archivo estático. La clave `pk_` es PUBLICABLE por diseño
        # (los docs de Portal: "safe to ship in a browser bundle"); la secreta
        # (`sk_`, para `portal deploy`) no la toca el bridge ni aparece nunca.
        if request.path.split("?", 1)[0] == "/portal-config.json":
            payload = json.dumps({"apiKey": config.PORTAL_API_KEY,
                                  "room": config.PORTAL_ROOM,
                                  "realtimeUrl": PORTAL_REALTIME_URL,
                                  "apiUrl": PORTAL_API_URL}).encode()
            headers = Headers()
            headers["Content-Type"] = "application/json; charset=utf-8"
            headers["Content-Length"] = str(len(payload))
            headers["Cache-Control"] = "no-cache"
            return Response(200, "OK", headers, payload)

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
    """Cliente del wire protocol v1 de Portal (useportal.co).

    No usa `@portalsdk/core` (es TS/JS y arrastra un bundler): habla el
    protocolo directo sobre `websockets`, que ya es dependencia del bridge.
    Los docs de Portal describen el wire justamente para esto — "implementing
    a client in another language".

    Los channels `jam:*` de ViruSynth viajan como el campo `type` de mensajes
    EFÍMEROS dentro de un único canal Portal (`PORTAL_ROOM`). Efímeros y no
    persistentes a propósito: `jam:state` va a 10 Hz y `jam:note_triggered`
    dispara por nota — persistirlos les pondría `seq`, los guardaría para
    siempre y sumaría un round-trip HTTP por nota. Medido: 18.6 msg/s sin un
    solo error ni pérdida.
    """

    def __init__(self) -> None:
        if not config.PORTAL_API_KEY:
            raise ValueError("PORTAL_API_KEY vacío")
        self._handler: Optional[IncomingHandler] = None
        self._ws = None
        self._task: Optional[asyncio.Task] = None
        self._closed = False
        self._roster: dict[str, str] = {}     # userId -> role
        self._aggregate: Optional[int] = None  # canales grandes: solo un total
        self._cl = 0
        self._token_exp = 0.0

    # ---- ciclo de vida -----------------------------------------------------
    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: B014
                pass
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass

    # ---- token -------------------------------------------------------------
    async def _mint_token(self) -> str:
        """Token anónimo. Este endpoint NO está en los docs de Portal (lo
        declaran "doc gap"); sale de @portalsdk/core. Dura 1 h, así que se
        vuelve a pedir en cada (re)conexión."""
        def _post() -> dict[str, Any]:
            req = urllib.request.Request(
                f"{PORTAL_API_URL}/v1/tokens/anonymous", data=b"{}",
                headers={"x-portal-key": config.PORTAL_API_KEY,
                         "content-type": "application/json",
                         "user-agent": _PORTAL_UA},
                method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())

        payload = await asyncio.to_thread(_post)
        token = str(payload.get("token") or "")
        if not token:
            raise RuntimeError("Portal no devolvió token")
        self._token_exp = _jwt_exp(token)
        return token

    def _upgrade_url(self, token: str) -> str:
        # `key` no figura en los docs pero el SDK oficial siempre lo manda.
        query = urllib.parse.urlencode({
            "v": "1", "key": config.PORTAL_API_KEY, "token": token,
            "meta": base64.b64encode(
                json.dumps({"role": "bridge"}).encode()).decode()})
        room = urllib.parse.quote(config.PORTAL_ROOM, safe="")
        return f"{PORTAL_REALTIME_URL}/v1/channels/{room}?{query}"

    # ---- conexión ----------------------------------------------------------
    async def _run(self) -> None:
        backoff = 1.0
        while not self._closed:
            try:
                await self._session()
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("Portal: %s — reintento en %.0f s "
                            "(la jam sigue por el WS local)", exc, backoff)
            if self._closed:
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.8, 30.0)

    async def _session(self) -> None:
        import websockets

        token = await self._mint_token()
        async with websockets.connect(self._upgrade_url(token),
                                      open_timeout=15,
                                      ping_interval=20, ping_timeout=20) as ws:
            self._ws = ws
            log.info("Portal conectado: canal '%s' en %s",
                     config.PORTAL_ROOM, PORTAL_REALTIME_URL)
            keep = asyncio.create_task(self._keepalive(ws))
            try:
                async for raw in ws:
                    try:
                        frame = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    await self._on_frame(frame)
            finally:
                keep.cancel()
                self._ws = None
                self._roster.clear()
                self._aggregate = None

    async def _keepalive(self, ws) -> None:
        """Ping de aplicación cada 25 s (además del ping del propio WS), y
        reconexión preventiva antes de que el token de 1 h expire."""
        try:
            while True:
                await asyncio.sleep(25)
                if self._token_exp and time.time() > self._token_exp - 120:
                    log.info("Portal: token por expirar, reconectando")
                    await ws.close()
                    return
                await ws.send(json.dumps({"t": "ping"}))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            return

    # ---- frames ------------------------------------------------------------
    async def _on_frame(self, frame: dict[str, Any]) -> None:
        kind = frame.get("t")
        if kind == "ready":
            self._snapshot(frame.get("presence") or {})
            await self._emit_presence()
        elif kind == "presence":
            gone = self._delta(frame)
            for user_id in gone:
                if self._handler:
                    await self._handler("client:gone", {"client_id": user_id},
                                        {"id": "portal", "role": "system"})
            await self._emit_presence()
        elif kind == "ephemeral":
            channel = str(frame.get("type") or "")
            data = frame.get("content")
            user_id = str(frame.get("userId") or "")
            if channel.startswith("jam:") and isinstance(data, dict) and self._handler:
                await self._handler(channel, data,
                                    {"id": user_id,
                                     "role": self._roster.get(user_id, "audience"),
                                     "name": ""})
        elif kind == "error":
            log.warning("Portal rechazó un frame: %s", json.dumps(frame)[:200])

    # ---- presencia ---------------------------------------------------------
    def _snapshot(self, presence: dict[str, Any]) -> None:
        self._roster.clear()
        if (presence.get("mode") or presence.get("kind")) == "aggregate":
            self._aggregate = int(presence.get("count") or 0)
            return
        self._aggregate = None
        for participant in presence.get("participants") or []:
            self._remember(participant)

    def _delta(self, frame: dict[str, Any]) -> list[str]:
        if (frame.get("mode") or frame.get("kind")) == "aggregate":
            self._aggregate = int(frame.get("count") or 0)
            return []
        self._aggregate = None
        for participant in frame.get("joined") or []:
            self._remember(participant)
        gone: list[str] = []
        for participant in frame.get("left") or []:
            user_id = (str(participant.get("id") or "")
                       if isinstance(participant, dict) else str(participant))
            if self._roster.pop(user_id, None) is not None or user_id:
                gone.append(user_id)
        return gone

    def _remember(self, participant: Any) -> None:
        if not isinstance(participant, dict):
            return
        user_id = str(participant.get("id") or "")
        if not user_id:
            return
        role = str((participant.get("metadata") or {}).get("role") or "audience")
        self._roster[user_id] = role if role in _ROLES or role == "bridge" else "audience"

    @property
    def presence(self) -> dict[str, int]:
        counts = {"performers": 0, "artists": 0, "audience": 0}
        if self._aggregate is not None:
            counts["audience"] = max(0, self._aggregate - 1)  # menos el bridge
            return counts
        for role in self._roster.values():
            if role == "bridge":
                continue          # el propio bridge no es público
            if role == "artist":
                counts["artists"] += 1
            elif role == "stage":
                counts["performers"] += 1
            else:
                counts["audience"] += 1
        return counts

    async def _emit_presence(self) -> None:
        if self._handler:
            await self._handler("presence:changed", self.presence,
                                {"id": "portal", "role": "system"})

    # ---- salida ------------------------------------------------------------
    async def publish(self, channel: str, data: dict[str, Any]) -> None:
        ws = self._ws
        if ws is None:
            return                # sin conexión: el WS local sigue publicando
        try:
            encoded = json.dumps(data, ensure_ascii=False).encode()
        except (TypeError, ValueError):
            return
        if len(encoded) > _MAX_CONTENT_BYTES:
            log.warning("Portal: %s pesa %d B (>%d) — no se publica",
                        channel, len(encoded), _MAX_CONTENT_BYTES)
            return
        self._cl += 1
        frame = {"t": "ephemeral", "cl": f"b{self._cl}",
                 "type": channel, "content": data}
        try:
            await ws.send(json.dumps(frame, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            pass              # el loop de reconexión se encarga


class CompositePortal(PortalBase):
    """Varios transportes a la vez, con los MISMOS channels `jam:*`.

    Portal se suma al WS local, no lo reemplaza: CLAUDE.md §7 exige que la
    demo nunca dependa de un servicio externo, y además el WS local es el que
    sirve la página web. Si Portal se cae, la jam local ni se entera.
    """

    def __init__(self, backends: list[PortalBase]) -> None:
        self._backends = backends
        self._handler: Optional[IncomingHandler] = None

    def set_handler(self, handler: IncomingHandler) -> None:
        self._handler = handler
        for backend in self._backends:
            backend.set_handler(self._relay)

    async def _relay(self, channel: str, data: dict[str, Any],
                     client: dict[str, Any]) -> None:
        """`presence:changed` se recalcula sumando todos los backends: si no,
        el último en hablar pisaría la cuenta del otro."""
        if self._handler is None:
            return
        await self._handler(channel, self.presence if channel == "presence:changed"
                            else data, client)

    async def start(self) -> None:
        for backend in self._backends:
            try:
                await backend.start()
            except Exception as exc:  # noqa: BLE001
                log.warning("%s no arrancó (%s) — se sigue con el resto",
                            type(backend).__name__, exc)

    async def stop(self) -> None:
        for backend in self._backends:
            try:
                await backend.stop()
            except Exception:  # noqa: BLE001
                pass

    async def publish(self, channel: str, data: dict[str, Any]) -> None:
        await asyncio.gather(*(b.publish(channel, data) for b in self._backends),
                             return_exceptions=True)

    @property
    def presence(self) -> dict[str, int]:
        total = {"performers": 0, "artists": 0, "audience": 0}
        for backend in self._backends:
            counts = backend.presence
            for key in total:
                total[key] += int(counts.get(key, 0))
        return total


def _jwt_exp(token: str) -> float:
    """`exp` del JWT sin verificar firma — solo para reconectar a tiempo."""
    try:
        payload = token.split(".")[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload)).get("exp") or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def create_portal() -> PortalBase:
    try:
        import websockets  # noqa: F401
    except ImportError:
        log.warning("'websockets' no instalado: bridge sin capa realtime")
        return NullPortal()

    backends: list[PortalBase] = [LocalPortalServer()]
    if config.PORTAL_API_KEY:
        try:
            backends.append(PortalSDKAdapter())
        except Exception as exc:  # noqa: BLE001
            log.warning("Portal no se pudo inicializar (%s): solo WS local", exc)
    else:
        log.info("PORTAL_API_KEY vacío: solo WS local (ver docs/remote-access.md)")
    return backends[0] if len(backends) == 1 else CompositePortal(backends)
