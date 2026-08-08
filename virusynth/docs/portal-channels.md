# Channels realtime `jam:*` — Portal y fallback local

La capa realtime transporta JSON por channels con namespace `jam:*`. Hoy los
sirve el **servidor WS local del bridge** (`ws://<host-del-bridge>:8765`);
cuando exista acceso al SDK de Portal, `PortalSDKAdapter` publica/consume los
MISMOS channels y nada más cambia.

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

## Cómo hacer el swap al SDK real de Portal

1. Implementar `PortalSDKAdapter` en `bridge/portal_client.py` respetando la
   interfaz `PortalBase` (`start`, `stop`, `publish`, `set_handler`, `presence`).
2. Mapear los mensajes entrantes del SDK a `handler(channel, data, client)`
   con `client = {"id", "role", "name"}`.
3. En `web/js/portal-client.js`, sustituir el transporte WS por el cliente JS
   del SDK manteniendo `connect/on/publish`.
4. Definir `PORTAL_API_KEY` (y `PORTAL_ROOM`) en `.env` — `create_portal()`
   elegirá el adaptador automáticamente.
