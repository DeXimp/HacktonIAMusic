# Acceso remoto — audiencia/escenario en OTRA red

## Primero, qué es "Portal" realmente acá

"Portal" es el sponsor del hackathon (*Realtime Hackathon by Portal*) — la
idea original del proyecto es que su SDK real fuera la capa de transporte
que conecta gente en cualquier red, sin que ViruSynth tenga que resolver
NAT/hosting por su cuenta. **Ese SDK nunca se integró**: `PortalSDKAdapter`
en `bridge/portal_client.py` es un punto de extensión que hoy lanza
`NotImplementedError` a propósito —

```python
class PortalSDKAdapter(PortalBase):
    """PUNTO DE INTEGRACIÓN con el SDK real de Portal.
    Cuando el hackathon entregue SDK/credenciales: implementar start/publish...
    """
```

— porque nunca tuvimos credenciales/SDK reales para implementarlo. No es
algo que se pueda simular de forma honesta sin acceso al servicio real. Si
en algún momento el hackathon los entrega, ese archivo es exactamente donde
va la integración — el resto del bridge no se entera del cambio (mismos
channels `jam:*`, ver `docs/portal-channels.md`).

Mientras tanto, `create_portal()` usa `LocalPortalServer`: un WebSocket
propio, siempre activo, que es el que de verdad mueve la jam hoy (CLAUDE.md
§7 — "Portal sin SDK/credenciales → servidor WS local, mismos channels").

## Por qué antes esto solo andaba en la misma red (LAN)

`Portal.url` en `web/js/portal-client.js` se conecta a
`ws://<host de la página>:8765`. Si alguien en OTRA red (no tu WiFi/LAN)
abre esa URL, no llega a nada — tu máquina está detrás de tu router/NAT, sin
puerto abierto al mundo. Por eso hasta ahora solo "audiencia en el mismo
WiFi" funcionaba de verdad.

## Qué se cambió

1. **`bridge/portal_client.py`** ahora sirve la carpeta `web/` desde el
   *mismo* puerto del WebSocket (`process_request` de la librería
   `websockets` distingue el handshake WS de una request HTTP normal y
   sirve el archivo correspondiente). Un solo proceso, un solo puerto, un
   solo link para compartir — ya no hace falta el `python -m http.server`
   aparte.
2. **`web/js/portal-client.js`** arma la URL del WebSocket a partir de
   `location.protocol`/`location.host` de la página que ya se cargó, en vez
   de asumir `ws://` y el puerto 8765 fijos. Esto es necesario para que
   funcione detrás de un túnel HTTPS (los navegadores bloquean `ws://`
   desde una página `https://` por *mixed content*; y el puerto público de
   un túnel no es 8765).
3. **`scripts/start-all.ps1`** ahora tiene un flag `-Tunnel`.

Con esto, exponer la jam a cualquier red es: correr un túnel que apunte al
puerto del bridge (default 8765, o el que haya elegido `start-all.ps1` si
ese estaba ocupado) y compartir la URL pública que te devuelve.

## Cómo usarlo (con ngrok)

[ngrok](https://ngrok.com/download) es la forma más simple sin infraestructura
propia — gratis para esto, no requiere abrir puertos en tu router.

```powershell
# una vez: instalar ngrok y loguearte (cuenta gratis)
ngrok config add-authtoken <tu-token-de-ngrok.com>

# arranca todo + el túnel
powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1 -Tunnel
```

El script detecta si `ngrok` está en el PATH, lo levanta apuntando al
puerto del bridge, y trata de leer la URL pública de la API local de ngrok
(`http://127.0.0.1:4040`) para imprimirla directo en la consola:

```
Link público (cualquier red) -- compartilo con audiencia/escenario remoto:
  Audiencia:  https://xxxx-xx-xx-xxx-xx.ngrok-free.app/?role=audience
  Artistas:   https://xxxx-xx-xx-xxx-xx.ngrok-free.app/?role=artist
  Escenario:  https://xxxx-xx-xx-xxx-xx.ngrok-free.app/?role=stage
```

Si no lo encuentra o la API de ngrok todavía no respondió, revisá la
ventana propia de ngrok — ahí también aparece la URL (`Forwarding`).

Sin `-Tunnel`, `start-all.ps1` sigue funcionando igual que antes para LAN
local (imprime las URLs con la IP de tu máquina).

## Sobre el audio: ¿qué escucha alguien conectado desde otra red?

El audio "real" del instrumento sigue sonando 100% local en Pure Data — eso
**no** viaja por la red, ni por el túnel (ver CLAUDE.md §2). Lo que sí llega
a cualquier red, local o remota, es el canal de control (`jam:state`,
`jam:note_triggered`, etc.) que ya usa el orbe visual — y desde hace poco,
también alimenta `web/js/audio-engine.js`: un mini-sintetizador que corre en
el navegador de quien esté escuchando (ver `docs/portal-channels.md`,
sección "Audio para la audiencia"). Con el túnel activo, alguien en otra
ciudad puede tocar "🔈 Escuchar en vivo" y va a escuchar una aproximación en
tiempo real de lo que está tocando el performer — no un streaming del audio
exacto de Pd, pero sí la misma escala, las mismas notas, el mismo groove.

## Nota de seguridad (a propósito, no un descuido)

Un link de ngrok es público: cualquiera que lo tenga puede entrar como
audiencia (votar) o artista (proponer patrones) sin login. Es el diseño
declarado del proyecto ("audiencia remota que vota", "artistas remotos que
proponen patrones" — CLAUDE.md §1), no algo que haya que cerrar con
autenticación para esta demo. Si en algún momento hace falta restringir
quién entra, es una capa aparte (autenticación en `LocalPortalServer` o en
el SDK real de Portal) — no se agregó acá para no inventar un requisito que
nadie pidió.
