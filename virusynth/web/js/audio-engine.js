/* Motor de audio para la audiencia remota — Web Audio API, stdlib del
   navegador, sin dependencias ni CDNs.

   El audio "real" de ViruSynth sigue siendo 100% de Pure Data (CLAUDE.md
   §2): esto NO es un streaming de ese audio, es un mini-sintetizador que
   corre en cada navegador y toca las mismas notas/parámetros que ya viajan
   por WebSocket (jam:state a 10 Hz, jam:note_triggered por cada nota) —
   igual que la IA nunca genera audio directamente, el navegador tampoco
   recibe bytes de audio: recibe control musical y sintetiza localmente.
   Eso evita necesitar Icecast/captura de loopback/infraestructura nueva, y
   escala sin importar cuánta gente esté escuchando (el ancho de banda por
   oyente sigue siendo el mismo canal de control liviano que ya existía).

   No es un espejo sample-accurate del DSP de Pd — es una aproximación
   liviana (osciladores detunados + sub, filtro, envolvente, delay y una
   reverb algorítmica con impulso generado en el momento). Suficiente para
   que la sala remota sienta lo que está pasando; el instrumento real sigue
   sonando por los parlantes de Pd.

   Arranca apagado a propósito: si la audiencia está físicamente en la sala
   ya escucha los parlantes reales, y los navegadores exigen un gesto del
   usuario antes de reproducir audio (política de autoplay) — por eso
   `enable()` debe llamarse desde un click. */

export class AudioEngine {
  constructor() {
    this.ctx = null;
    this.enabled = false;
    this.master = null;
    this.filter = null;
    this.delayNode = null;
    this.delayFeedback = null;
    this.delayWet = null;
    this.reverbWet = null;
    this.dryGain = null;
    this.listenGain = 0.7;    // volumen local del oyente, separado del vs-vol del performer
    this.jam = { cutoff: 1200, volume: 0.8, fx: { reverb: 0.35, delay: 0.25 } };
  }

  get supported() {
    return typeof (window.AudioContext || window.webkitAudioContext) === "function";
  }

  /* Debe llamarse desde un gesto del usuario (click) — política de autoplay. */
  async enable() {
    if (this.enabled || !this.supported) return;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    this.ctx = new Ctx();
    await this.ctx.resume();
    this._buildGraph();
    this.enabled = true;
  }

  async disable() {
    if (!this.enabled) return;
    this.enabled = false;
    const ctx = this.ctx;
    this.ctx = null;
    try { await ctx.close(); } catch { /* ya cerrado */ }
  }

  setListenVolume(v) {
    this.listenGain = Math.max(0, Math.min(1, v));
    if (this.enabled) this._applyMasterGain();
  }

  _buildGraph() {
    const ctx = this.ctx;

    this.master = ctx.createGain();
    this.filter = ctx.createBiquadFilter();
    this.filter.type = "lowpass";
    this.filter.frequency.value = this.jam.cutoff;
    this.filter.Q.value = 1.4;

    this.dryGain = ctx.createGain();
    this.dryGain.gain.value = 1;

    this.delayNode = ctx.createDelay(1.2);
    this.delayNode.delayTime.value = 0.32;
    this.delayFeedback = ctx.createGain();
    this.delayFeedback.gain.value = 0.35;
    this.delayWet = ctx.createGain();
    this.delayWet.gain.value = this.jam.fx.delay ?? 0.25;
    this.delayNode.connect(this.delayFeedback);
    this.delayFeedback.connect(this.delayNode);
    this.delayNode.connect(this.delayWet);

    this.reverbNode = ctx.createConvolver();
    this.reverbNode.buffer = this._makeImpulse(2.2, 2.4);
    this.reverbWet = ctx.createGain();
    this.reverbWet.gain.value = this.jam.fx.reverb ?? 0.35;
    this.reverbNode.connect(this.reverbWet);

    this.filter.connect(this.dryGain);
    this.filter.connect(this.delayNode);
    this.filter.connect(this.reverbNode);
    this.dryGain.connect(this.master);
    this.delayWet.connect(this.master);
    this.reverbWet.connect(this.master);
    this.master.connect(ctx.destination);

    this._applyMasterGain();
  }

  _applyMasterGain() {
    if (!this.enabled) return;
    const target = Math.max(0, Math.min(1, this.jam.volume)) * this.listenGain * 0.6;
    this.master.gain.setTargetAtTime(target, this.ctx.currentTime, 0.05);
  }

  /* Impulso de ruido con decaimiento exponencial — reverb "pobre" 100%
     generada en el momento, sin archivo de impulso que cargar. */
  _makeImpulse(durationS, decay) {
    const rate = this.ctx.sampleRate;
    const length = Math.max(1, Math.floor(rate * durationS));
    const impulse = this.ctx.createBuffer(2, length, rate);
    for (let ch = 0; ch < 2; ch++) {
      const data = impulse.getChannelData(ch);
      for (let i = 0; i < length; i++) {
        data[i] = (Math.random() * 2 - 1) * (1 - i / length) ** decay;
      }
    }
    return impulse;
  }

  /* ---- entrada continua: jam:state (10 Hz) ---- */
  setState(s) {
    if (!s) return;
    if (typeof s.cutoff === "number") this.jam.cutoff = s.cutoff;
    if (typeof s.volume === "number") this.jam.volume = s.volume;
    if (s.fx) Object.assign(this.jam.fx, s.fx);
    if (!this.enabled) return;
    const now = this.ctx.currentTime;
    this.filter.frequency.setTargetAtTime(this.jam.cutoff, now, 0.03);
    this.delayWet.gain.setTargetAtTime(this.jam.fx.delay ?? 0.25, now, 0.15);
    this.reverbWet.gain.setTargetAtTime(this.jam.fx.reverb ?? 0.35, now, 0.15);
    this._applyMasterGain();
  }

  /* ---- disparo de nota: jam:note_triggered ---- */
  noteOn(midi, velocity) {
    if (!this.enabled || !this.ctx) return;
    const ctx = this.ctx;
    const now = ctx.currentTime;
    const freq = 440 * 2 ** ((midi - 69) / 12);
    const peak = Math.max(0.05, Math.min(1, (velocity || 80) / 127));

    const voice = ctx.createGain();
    voice.gain.setValueAtTime(0, now);
    voice.gain.linearRampToValueAtTime(peak * 0.5, now + 0.008);
    voice.gain.exponentialRampToValueAtTime(0.001, now + 0.42);

    const mix = ctx.createGain();
    mix.gain.value = 0.28;
    const subGain = ctx.createGain();
    subGain.gain.value = 0.22;

    const oscs = [
      this._mkOsc(freq, "sawtooth", 0),
      this._mkOsc(freq, "sawtooth", 10),
      this._mkOsc(freq, "sawtooth", -10),
    ];
    for (const o of oscs) o.connect(mix);
    const sub = this._mkOsc(freq / 2, "sine", 0);
    sub.connect(subGain);

    mix.connect(voice);
    subGain.connect(voice);
    voice.connect(this.filter);

    const stopAt = now + 0.5;
    for (const o of [...oscs, sub]) {
      o.start(now);
      o.stop(stopAt);
    }
    oscs[0].addEventListener("ended", () => {
      try { voice.disconnect(); mix.disconnect(); subGain.disconnect(); } catch { /* ya desconectado */ }
    });
  }

  _mkOsc(freq, type, detuneCents) {
    const osc = this.ctx.createOscillator();
    osc.type = type;
    osc.frequency.value = freq;
    osc.detune.value = detuneCents;
    return osc;
  }
}
