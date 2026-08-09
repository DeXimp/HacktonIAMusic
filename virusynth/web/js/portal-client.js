/* Cliente realtime de ViruSynth.
   Hoy: WebSocket local del bridge — servido desde el MISMO origen que esta
   página (bridge/portal_client.py sirve la web/ y el WebSocket en el mismo
   puerto), así que un solo túnel (ngrok o similar) alcanza para que alguien
   en otra red entre como audiencia/artista/escenario — ver
   docs/remote-access.md. `wss://` se usa automáticamente cuando la página
   se cargó por HTTPS (los navegadores bloquean `ws://` desde una página
   https por mixed content), y el puerto se toma de `location.host` en vez
   de estar fijo, porque detrás de un túnel el puerto público no es 8765.
   Mañana: PUNTO DE SWAP al SDK de Portal — misma interfaz pública
   (connect / on / publish), mismos channels `jam:*`. Ver docs/portal-channels.md. */

export class Portal {
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
