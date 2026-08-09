/* Cliente de Portal (useportal.co) hablando el wire protocol v1 directo, en JS
   vanilla — sin npm, sin bundler, sin CDN (CLAUDE.md §3).

   Por qué no `@portalsdk/core`: es un paquete npm que arrastra `partysocket` y
   asume un build step. El wire protocol de Portal está documentado justamente
   para esto ("implementing a client in another language"), y son ~120 líneas.

   Interfaz pública IDÉNTICA a la del cliente local de portal-client.js
   (connect / on / onStatus / publish), así que app.js, audience-ui.js y
   artist-ui.js no se enteran de cuál de los dos transportes está activo.

   Los channels `jam:*` viajan como el campo `type` de mensajes EFÍMEROS
   dentro de un solo canal Portal. Efímeros a propósito: `jam:state` va a
   10 Hz y las notas disparan más rápido todavía; persistirlos les pondría
   `seq` y los guardaría para siempre sin ninguna razón.

   Ver docs/portal-channels.md y docs/remote-access.md. */

const PING_MS = 25000;          // el wire protocol espera un ping ~cada 25 s
const REFRESH_MARGIN_MS = 120000;   // reconectar 2 min antes de que expire el token

/* btoa() rompe con acentos; el nombre del artista puede tenerlos. */
function b64utf8(obj) {
  const bytes = new TextEncoder().encode(JSON.stringify(obj));
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

/* `exp` del JWT sin verificar firma — solo para reconectar a tiempo. */
function jwtExpMs(token) {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const exp = JSON.parse(atob(part + "=".repeat((4 - part.length % 4) % 4))).exp;
    return typeof exp === "number" ? exp * 1000 : 0;
  } catch { return 0; }
}

export class PortalRemote {
  constructor(role, name = "", config) {
    this.role = role;
    this.name = name;
    this.config = config;          // { apiKey, room, realtimeUrl, apiUrl }
    this.handlers = new Map();     // channel -> Set<cb>
    this.statusCbs = new Set();
    this.ws = null;
    this.retryMs = 500;
    this.closed = false;
    this.cl = 0;
    this.timers = [];
  }

  /* El token anónimo lo emite Portal a partir de la clave publicable. Este
     endpoint NO está en docs.useportal.co (lo marcan como "doc gap"); sale de
     leer @portalsdk/core. Dura 1 h. */
  async _mintToken() {
    const res = await fetch(`${this.config.apiUrl}/v1/tokens/anonymous`, {
      method: "POST",
      headers: { "x-portal-key": this.config.apiKey,
                 "content-type": "application/json" },
      body: "{}",
    });
    if (!res.ok) throw new Error(`Portal /v1/tokens/anonymous -> ${res.status}`);
    const { token } = await res.json();
    if (!token) throw new Error("Portal no devolvió token");
    return token;
  }

  _url(token) {
    // `key` no figura en los docs pero el SDK oficial siempre lo manda.
    const query = new URLSearchParams({
      v: "1", key: this.config.apiKey, token,
      meta: b64utf8({ role: this.role, name: this.name.slice(0, 40) }),
    });
    const room = encodeURIComponent(this.config.room);
    return `${this.config.realtimeUrl}/v1/channels/${room}?${query}`;
  }

  async connect() {
    if (this.closed) return;
    this._setStatus("connecting");
    let token;
    try {
      token = await this._mintToken();
    } catch (err) {
      console.warn("[portal]", err.message);
      this._scheduleRetry();
      return;
    }
    if (this.closed) return;

    let ws;
    try {
      ws = new WebSocket(this._url(token));
    } catch {
      this._scheduleRetry();
      return;
    }
    this.ws = ws;

    ws.onmessage = (ev) => {
      let frame;
      try { frame = JSON.parse(ev.data); } catch { return; }
      if (frame.t === "ready") {
        this.retryMs = 500;
        this._setStatus("open");
      } else if (frame.t === "ephemeral") {
        const set = this.handlers.get(frame.type);
        if (set) for (const cb of set) cb(frame.content);
      } else if (frame.t === "error") {
        console.warn("[portal] frame rechazado:", frame.code, frame.reason || "");
      }
    };
    ws.onclose = () => {
      this._clearTimers();
      this._setStatus("closed");
      this._scheduleRetry();
    };
    ws.onerror = () => { try { ws.close(); } catch { /* ya cerrado */ } };
    ws.onopen = () => {
      this._clearTimers();
      this.timers.push(setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('{"t":"ping"}');
      }, PING_MS));
      // El token muere a la hora: cerrar antes y reconectar re-emitiéndolo.
      const expMs = jwtExpMs(token) - Date.now() - REFRESH_MARGIN_MS;
      if (expMs > 0) {
        this.timers.push(setTimeout(() => { try { ws.close(); } catch { /**/ } }, expMs));
      }
    };
  }

  close() {
    this.closed = true;
    this._clearTimers();
    try { this.ws?.close(); } catch { /* ya cerrado */ }
  }

  _clearTimers() {
    for (const t of this.timers) { clearInterval(t); clearTimeout(t); }
    this.timers = [];
  }

  _scheduleRetry() {
    if (this.closed) return;
    setTimeout(() => this.connect(), this.retryMs);
    this.retryMs = Math.min(this.retryMs * 1.7, 5000);
  }

  on(channel, cb) {
    if (!this.handlers.has(channel)) this.handlers.set(channel, new Set());
    this.handlers.get(channel).add(cb);
    return this;
  }

  onStatus(cb) { this.statusCbs.add(cb); return this; }
  _setStatus(s) { for (const cb of this.statusCbs) cb(s); }

  publish(channel, data) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.cl += 1;
    this.ws.send(JSON.stringify({
      t: "ephemeral", cl: `c${this.cl}`, type: channel, content: data,
    }));
  }
}
