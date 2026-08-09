# Channels realtime `jam:*` — Portal y fallback local

La capa realtime transporta JSON por channels con namespace `jam:*`. Hoy los
sirve el **servidor WS local del bridge** (`ws://<host-del-bridge>:8765`),
que además sirve `web/` por HTTP en ese mismo puerto — un solo puerto/link
para todo, tunneleable con `start-all.ps1 -Tunnel` para gente en otra red
(ver `docs/remote-access.md`). Cuando exista acceso al SDK real de "Portal"
(el sponsor del hackathon; hoy sigue siendo un punto de extensión sin
implementar, ver `docs/remote-access.md`), `PortalSDKAdapter` publica/consume
los MISMOS channels y nada más cambia.

## Envelope del WS local

```json
// cliente → bridge, al conectar (una vez):
{"type": "hello", "role": "audience" | "artist" | "stage", "name": "opcional"}

// cliente → bridge, para publicar:
{"type": "publish", "channel": "jam:votes:cast", "data": { }}

// bridge → clientes (broadcast):
{"type": "state", "channel": "jam:state", "data": { }}

// bridge → cliente (respuesta al hello):
{"type": "welcome", "client_id": "ab12cd34", "role": "audience"}
```

## Channels

| Channel | Dirección | Cadencia | Payload |
|---|---|---|---|
| `jam:state` | bridge → todos | 10 Hz | `{bpm, scale, root_note, volume, cutoff, fx:{reverb,delay,distortion}, amplitude, current_notes[], active_pattern, pattern_author, performer_active, session}` |
| `jam:votes:cast` | cliente → bridge | por interacción | voto parcial: `{scale?}` `{bpm?}` `{fx?:{reverb?|delay?|distortion?}}` — última escritura por cliente gana |
| `jam:votes` | bridge → todos | 1 Hz (si hay votos) | agregado: `{scale_votes:{...}, bpm_avg, fx_avg:{...}, voters}` |
| `jam:artist_suggestions` | cliente → bridge → rebroadcast | por envío | `{artist_id, suggestion:{type:"note_pattern", notes[], steps, duration, resolved_notes[], changes[{from,to}]}}` — el bridge añade `resolved_notes`/`changes` al rebroadcast |
| `jam:ai_director` | bridge → todos | cada ~7 s | `{action, value, reasoning, harmonic_resolution, source:"claude"|"reglas_locales", timestamp}` |
| `jam:presence` | bridge → todos | en cambios | `{performers, artists, audience}` |
| `jam:note_triggered` | bridge → todos | por nota | `{note, velocity}` — eco de cada disparo real hacia Pd (`PdLink.trigger_note()`), lo consume `web/js/audio-engine.js` para tocar la misma nota en el mini-sintetizador del navegador |

### Audio para la audiencia (`web/js/audio-engine.js`)

El audio "real" sigue siendo 100% de Pure Data (CLAUDE.md §2) — no hay
streaming de esos bytes. Cada navegador con el botón "Escuchar en vivo"
activado corre su propio mini-sintetizador Web Audio (osciladores +
filtro + envolvente + delay + reverb algorítmica), alimentado por lo que
ya viaja por acá: `jam:state` (cutoff/volumen/FX, 10 Hz) para los
parámetros continuos, y `jam:note_triggered` para el disparo de cada nota.
No es un espejo sample-accurate del DSP de Pd, es una aproximación liviana
—suficiente para que la sala remota sienta lo que está pasando sin agregar
infraestructura de streaming de audio. Arranca apagado a propósito (evita
duplicar el sonido de quien ya está en la sala, y los navegadores exigen
un gesto del usuario antes de reproducir audio de todos modos).

### Acciones de `jam:ai_director`

| `action` | `value` |
|---|---|
| `change_scale` | string (`"E_minor"`) |
| `set_bpm` | int 60–180 |
| `set_fx` | `{reverb?|delay?|distortion?: 0–1}` |
| `harmonic_resolution` | null — detalle en `harmonic_resolution:{original_notes[], resolved_notes[], explanation}` |
| `no_change` | null |

## Política de aplicación (quién manda sobre qué)

- **FX**: se aplican en caliente con lerp del 15 % cada 0.5 s hacia `fx_avg`
  (la audiencia siente control inmediato).
- **BPM y escala**: los arbitra el IA Director (gradualidad ≤10 BPM y ≤0.2 FX
  por decisión; cooldown de escala 20 s).
- **Patrones de artista**: se cuantizan a la escala vigente al llegar y entran
  directo al secuenciador; si hubo choques, la IA lo comenta en el feed.

## Cómo viajan estos channels por Portal (useportal.co)

Portal está integrado: `PortalSDKAdapter` (`bridge/portal_client.py`) y
`PortalRemote` (`web/js/portal-remote.js`) hablan su **wire protocol v1**
directo — no se usa `@portalsdk/core`, que es npm + bundler y chocaría con la
regla "sin build step, sin CDNs" (CLAUDE.md §3). Los docs de Portal describen
el wire justamente para esto ("implementing a client in another language").

**Los ocho channels `jam:*` de arriba no cambian.** Viajan como el campo `type`
de mensajes **efímeros** dentro de un único canal Portal (`PORTAL_ROOM`,
default `virusynth-jam`):

```jsonc
// ViruSynth -> Portal            // Portal -> ViruSynth
{"t":"ephemeral","cl":"b7",       {"t":"ephemeral","userId":"anon_…",
 "type":"jam:state",               "type":"jam:votes:cast",
 "content":{…}}                    "content":{…}}
```

Efímeros y no persistentes a propósito: `jam:state` va a 10 Hz y
`jam:note_triggered` dispara por nota. Un publish persistente les pondría `seq`,
los guardaría para siempre y sumaría un round-trip HTTP por nota. Medido contra
el servicio real: **18.6 msg/s, 0 errores, 0 pérdidas**; `jam:state` pesa 290 B
de los 2048 que Portal permite por mensaje.

`jam:presence` lo sigue publicando el bridge, que cuenta los roles leyendo la
presencia del canal (cada cliente manda `meta={"role":…}` al conectarse). El
propio bridge entra con `role: "bridge"` y no se cuenta como público.

### Los dos transportes conviven

`create_portal()` devuelve un `CompositePortal` que publica en **Portal y en el
WS local a la vez**. El WS local no se va nunca: sirve la página web y es el
fallback que exige CLAUDE.md §7. Si Portal se cae, la jam local sigue sin
enterarse. En el navegador, `Portal` (`web/js/portal-client.js`) elige
transporte al conectar: si `/portal-config.json` trae clave *y* Portal responde,
usa Portal; si no, el WS local.

### Dos detalles que NO están en docs.useportal.co

Salieron de leer `@portalsdk/core@0.1.5` y están verificados contra el servicio:

1. **Token anónimo** (los docs lo marcan como *"doc gap"*):
   `POST https://api.useportal.co/v1/tokens/anonymous`, header
   `x-portal-key: pk_…`, body `{}` → `{"token": "<jwt>"}`. Dura 1 h.
2. **El WebSocket lleva `key`** además de `token`:
   `wss://realtime.useportal.co/v1/channels/{room}?v=1&key=pk_…&token=<jwt>`.

Además, `api.useportal.co` está detrás de Cloudflare: con el User-Agent por
defecto de `urllib` devuelve 403 (error 1010) — hay que mandar uno de navegador.

### Configuración

`PORTAL_API_KEY` y `PORTAL_ROOM` en `.env` (nunca en `.env.example`, que sí se
versiona). La clave `pk_` es **publicable** por diseño —los docs de Portal dicen
"safe to ship in a browser bundle"—, y el bridge se la sirve al navegador en
`/portal-config.json`. La clave secreta (`sk_`, solo para `portal deploy`) no la
usa el proyecto. Con `PORTAL_API_KEY` vacío, todo sigue funcionando por el WS
local.
