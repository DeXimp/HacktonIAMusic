/* Cliente realtime de ViruSynth. Hay DOS transportes con la misma interfaz y
   los mismos channels `jam:*`; la clase `Portal` de abajo elige uno al
   conectar, y el resto de la app (app.js, audience-ui.js, artist-ui.js) no se
   entera de cuál quedó activo:

   1. `PortalRemote` (portal-remote.js) — Portal (useportal.co). Cruza redes
      sin túnel ni port-forwarding: la audiencia entra desde cualquier lado.
      Se usa cuando el bridge reporta una clave en /portal-config.json.
   2. `LocalPortal` (acá abajo) — WebSocket local del bridge, servido desde el
      MISMO origen que esta página (bridge/portal_client.py sirve web/ y el WS
      en el mismo puerto). `wss://` sale solo cuando la página se cargó por
      HTTPS (los navegadores bloquean `ws://` desde https por mixed content) y
      el puerto se toma de `location.host`, porque detrás de un túnel el
      puerto público no es 8765. Ver docs/remote-access.md.

   El local es el fallback y NO desaparece: si Portal no responde, la jam
   sigue (CLAUDE.md §7 — la demo nunca depende de un servicio externo).
   Ver docs/portal-channels.md. */

import { PortalRemote } from "./portal-remote.js";

/* El bridge dice si hay Portal configurado. La clave que devuelve es
   PUBLICABLE por diseño (los docs de Portal: "safe to ship in a browser
   bundle"); la secreta nunca sale del .env del bridge. */
async function loadPortalConfig() {
  try {
    const res = await fetch("/portal-config.json", { cache: "no-store" });
    if (!res.ok) return null;
    const config = await res.json();
    return config && config.apiKey ? config : null;
  } catch {
    return null;   // web servida sin el bridge (p. ej. hosting estático)
  }
}

/* ¿Portal está realmente disponible, o solo configurado? Se prueba antes de
   elegirlo: una clave revocada o sin internet no puede tumbar la demo. */
async function portalReachable(config) {
  try {
    const res = await fetch(`${config.apiUrl}/v1/tokens/anonymous`, {
      method: "POST",
      headers: { "x-portal-key": config.apiKey, "content-type": "application/json" },
      body: "{}",
    });
    return res.ok;
  } catch {
    return false;
  }
}

/* Despachador: misma interfaz pública que cualquiera de los dos transportes.
   Guarda las suscripciones hechas antes de connect() y se las pasa al que
   termine eligiendo. */
export class Portal {
  constructor(role, name = "") {
    this.role = role;
    this.name = name;
    this.handlers = new Map();
    this.statusCbs = new Set();
    this.impl = null;
  }

  on(channel, cb) {
    if (!this.handlers.has(channel)) this.handlers.set(channel, new Set());
    this.handlers.get(channel).add(cb);
    this.impl?.on(channel, cb);
    return this;
  }

  onStatus(cb) {
    this.statusCbs.add(cb);
    this.impl?.onStatus(cb);
    return this;
  }

  publish(channel, data) { this.impl?.publish(channel, data); }

  async connect() {
    const config = await loadPortalConfig();
    if (config && await portalReachable(config)) {
      this.impl = new PortalRemote(this.role, this.name, config);
      console.info(`[portal] usando Portal (canal '${config.room}')`);
    } else {
      this.impl = new LocalPortal(this.role, this.name);
      console.info("[portal] usando el WebSocket local del bridge");
    }
    for (const [channel, set] of this.handlers) {
      for (const cb of set) this.impl.on(channel, cb);
    }
    for (const cb of this.statusCbs) this.impl.onStatus(cb);
    this.impl.connect();
  }
}

export class LocalPortal {
  constructor(role, name = "") {
    this.role = role;
    this.name = name;
    this.handlers = new Map();   // channel -> Set<cb>
    this.statusCbs = new Set();
    this.ws = null;
    this.retryMs = 500;
    this.closed = false;
    this.clientId = localStorage.getItem("vs-client-id")
      || (crypto.randomUUID ? crypto.randomUUID().slice(0, 8)
                            : Math.random().toString(36).slice(2, 10));
    localStorage.setItem("vs-client-id", this.clientId);
  }

  get url() {
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    // location.host incluye el puerto si no es el default (80/443) -- al
    // servir la web y el WS desde el mismo puerto (bridge/portal_client.py)
    // esto ya apunta al lugar correcto tanto en LAN como detrás de un túnel.
    const host = location.host || "localhost:8765";
    return `${scheme}//${host}`;
  }

  connect() {
    if (this.closed) return;
    this._setStatus("connecting");
    try {
      this.ws = new WebSocket(this.url);
    } catch {
      this._scheduleRetry();
      return;
    }
    this.ws.onopen = () => {
      this.retryMs = 500;
      this._setStatus("open");
      this._send({ type: "hello", role: this.role, name: this.name });
    };
    this.ws.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }
      if (msg.type === "state" && msg.channel) {
        const set = this.handlers.get(msg.channel);
        if (set) for (const cb of set) cb(msg.data);
      }
    };
    this.ws.onclose = () => { this._setStatus("closed"); this._scheduleRetry(); };
    this.ws.onerror = () => { try { this.ws.close(); } catch { /* ya cerrado */ } };
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
    this._send({ type: "publish", channel, data });
  }

  _send(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }
}

/* Utilidad compartida: limita la frecuencia de publicación de un control. */
export function throttle(fn, ms) {
  let last = 0, timer = null, pending = null;
  return (...args) => {
    pending = args;
    const now = Date.now();
    const fire = () => { last = Date.now(); timer = null; fn(...pending); };
    if (now - last >= ms) fire();
    else if (!timer) timer = setTimeout(fire, ms - (now - last));
  };
}
