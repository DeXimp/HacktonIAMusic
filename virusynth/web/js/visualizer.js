/* El orbe — firma visual de ViruSynth.
   Respira con la amplitud real de Pd, dibuja la constelación de la escala
   (12 clases de altura, las activas encendidas), lanza partículas por cada
   nota y ondula en ámbar cuando el Director IA decide. */

import { pitchClasses } from "./music.js";

const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

export class Visualizer {
  constructor(canvas, { idle = false } = {}) {
    this.cv = canvas;
    this.ctx = canvas.getContext("2d");
    this.idle = idle;              // modo portada: sin datos, respiración suave
    this.amp = 0;                  // amplitud suavizada
    this.targetAmp = idle ? 0.35 : 0;
    this.bpm = 112;
    this.scalePcs = pitchClasses("Am_pentatonic");
    this.particles = [];
    this.aiPulse = 0;              // radio de la onda ámbar (0 = inactiva)
    this.lastNotes = [];
    this.rot = 0;
    this._resize = this._resize.bind(this);
    addEventListener("resize", this._resize);
    this._resize();
    this._raf = requestAnimationFrame((t) => this._frame(t));
  }

  destroy() {
    cancelAnimationFrame(this._raf);
    removeEventListener("resize", this._resize);
  }

  /* ---- entrada de datos ---- */
  setState(s) {
    if (!s) return;
    this.targetAmp = Math.min(1, (s.amplitude ?? 0) * 1.15 + (s.performer_active ? 0.06 : 0));
    this.bpm = s.bpm || this.bpm;
    this.scalePcs = pitchClasses(s.scale);
    const notes = s.current_notes || [];
    const newest = notes[notes.length - 1];
    if (newest != null && newest !== this._lastSpawn) {
      this._lastSpawn = newest;
      this._spawn(newest);
    }
  }

  aiDecision() { this.aiPulse = 0.01; }

  _spawn(midi) {
    if (REDUCED) return;
    const angle = ((midi % 12) / 12) * Math.PI * 2 - Math.PI / 2;
    this.particles.push({
      angle: angle + (Math.random() - 0.5) * 0.15,
      dist: 0.22,
      speed: 0.0022 + Math.random() * 0.0015,
      life: 1,
      hue: this.scalePcs.has(((midi % 12) + 12) % 12) ? "cyan" : "magenta",
    });
    if (this.particles.length > 48) this.particles.shift();
  }

  /* ---- render ---- */
  _resize() {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    const r = this.cv.getBoundingClientRect();
    this.cv.width = Math.max(1, r.width * dpr);
    this.cv.height = Math.max(1, r.height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.w = r.width; this.h = r.height;
  }

  _frame(t) {
    this._raf = requestAnimationFrame((tt) => this._frame(tt));
    if (REDUCED && t - (this._lastT || 0) < 100) return;   // 10 fps si reduce-motion
    this._lastT = t;
    const { ctx, w, h } = this;
    if (!w || !h) return;
    ctx.clearRect(0, 0, w, h);

    const cx = w / 2, cy = h / 2;
    const base = Math.min(w, h) * 0.30;

    // respiración: sigue a la amplitud objetivo (o pulso lento en portada)
    if (this.idle) this.targetAmp = 0.3 + 0.12 * Math.sin(t / 1400);
    this.amp += (this.targetAmp - this.amp) * 0.12;
    const radius = base * (0.42 + this.amp * 0.5);
    if (!REDUCED) this.rot += 0.0009 + this.amp * 0.002;

    // halo exterior
    const halo = ctx.createRadialGradient(cx, cy, radius * 0.2, cx, cy, base * 1.5);
    halo.addColorStop(0, "rgba(138,125,255,0.16)");
    halo.addColorStop(1, "rgba(138,125,255,0)");
    ctx.fillStyle = halo;
    ctx.fillRect(0, 0, w, h);

    // constelación de la escala: 12 clases de altura
    for (let pc = 0; pc < 12; pc++) {
      const a = (pc / 12) * Math.PI * 2 - Math.PI / 2 + this.rot * 0.3;
      const px = cx + Math.cos(a) * base * 1.18;
      const py = cy + Math.sin(a) * base * 1.18;
      const inScale = this.scalePcs.has(pc);
      ctx.beginPath();
      ctx.arc(px, py, inScale ? 3.2 : 1.4, 0, Math.PI * 2);
      ctx.fillStyle = inScale ? "rgba(55,230,212,0.9)" : "rgba(139,147,184,0.35)";
      if (inScale) { ctx.shadowColor = "rgba(55,230,212,0.8)"; ctx.shadowBlur = 8; }
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    // anillo de tempo: marcador orbitando a la velocidad del BPM
    if (!this.idle) {
      const beat = (t / 1000) * (this.bpm / 60);
      const a = (beat % 4) / 4 * Math.PI * 2 - Math.PI / 2;
      ctx.beginPath();
      ctx.arc(cx + Math.cos(a) * base * 1.18, cy + Math.sin(a) * base * 1.18,
              2.6, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(233,236,255,0.85)";
      ctx.fill();
    }

    // partículas de notas
    for (const p of this.particles) {
      p.dist += p.speed;
      p.life -= 0.008;
      const px = cx + Math.cos(p.angle + this.rot) * base * (0.5 + p.dist);
      const py = cy + Math.sin(p.angle + this.rot) * base * (0.5 + p.dist);
      ctx.beginPath();
      ctx.arc(px, py, 2.4 * p.life + 0.6, 0, Math.PI * 2);
      ctx.fillStyle = p.hue === "cyan"
        ? `rgba(55,230,212,${0.75 * p.life})`
        : `rgba(255,79,163,${0.75 * p.life})`;
      ctx.fill();
    }
    this.particles = this.particles.filter((p) => p.life > 0);

    // onda ámbar del Director IA
    if (this.aiPulse > 0) {
      this.aiPulse += 0.02;
      const r = base * (0.6 + this.aiPulse * 1.4);
      const alpha = Math.max(0, 0.55 - this.aiPulse * 0.5);
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(255,180,84,${alpha})`;
      ctx.lineWidth = 2.5;
      ctx.stroke();
      if (alpha <= 0) this.aiPulse = 0;
    }

    // el orbe: núcleo con gradiente cian→violeta→magenta
    const orb = ctx.createRadialGradient(cx - radius * 0.25, cy - radius * 0.3,
                                         radius * 0.1, cx, cy, radius);
    orb.addColorStop(0, "rgba(233,236,255,0.95)");
    orb.addColorStop(0.35, "rgba(55,230,212,0.55)");
    orb.addColorStop(0.75, "rgba(138,125,255,0.35)");
    orb.addColorStop(1, "rgba(255,79,163,0.12)");
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fillStyle = orb;
    ctx.shadowColor = "rgba(138,125,255,0.6)";
    ctx.shadowBlur = 34;
    ctx.fill();
    ctx.shadowBlur = 0;

    // anillo fino del orbe
    ctx.beginPath();
    ctx.arc(cx, cy, radius + 6, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(233,236,255,0.18)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}
