/* Panel de artista: pad consciente de la escala + patrón de 8 pasos
   (canal jam:artist_suggestions). */

import { pitchClasses, noteName } from "./music.js";

const STEPS = 8;
const PADS = 16;   // dos octavas: root-12 … root+3 en 16 semitonos

export class ArtistUI {
  constructor(portal) {
    this.portal = portal;
    this.root = 69;
    this.scale = "Am_pentatonic";
    this.pattern = [];
    this.pad = document.getElementById("note-pad");
    this.lane = document.getElementById("pattern-lane");
    this.sendBtn = document.getElementById("pattern-send");
    this.status = document.getElementById("pattern-status");
    this._buildPads();
    this._buildLane();
    document.getElementById("pattern-clear").addEventListener("click", () => {
      this.pattern = [];
      this._renderLane();
    });
    this.sendBtn.addEventListener("click", () => this._send());
  }

  _padNotes() {
    const low = this.root - 12;
    return Array.from({ length: PADS }, (_, i) => low + i);
  }

  _buildPads() {
    this.pad.replaceChildren();
    for (const midi of this._padNotes()) {
      const b = document.createElement("button");
      b.className = "pad";
      b.dataset.midi = midi;
      b.innerHTML = `<span></span><small></small>`;
      b.firstChild.textContent = noteName(midi);
      b.lastChild.textContent = midi;
      b.addEventListener("click", () => this._tap(b, midi));
      this.pad.append(b);
    }
    this._markScale();
  }

  _markScale() {
    const pcs = pitchClasses(this.scale);
    for (const b of this.pad.children) {
      const midi = Number(b.dataset.midi);
      b.dataset.inscale = pcs.has(((midi % 12) + 12) % 12) ? "1" : "0";
    }
  }

  _tap(btn, midi) {
    btn.classList.add("pad--hit");
    setTimeout(() => btn.classList.remove("pad--hit"), 140);
    if (this.pattern.length >= STEPS) this.pattern.shift();
    this.pattern.push(midi);
    this._renderLane();
  }

  _buildLane() {
    this.lane.replaceChildren();
    for (let i = 0; i < STEPS; i++) {
      const cell = document.createElement("div");
      cell.className = "step";
      this.lane.append(cell);
    }
    this._renderLane();
  }

  _renderLane() {
    [...this.lane.children].forEach((cell, i) => {
      const midi = this.pattern[i];
      cell.classList.toggle("step--filled", midi != null);
      cell.textContent = midi != null ? noteName(midi) : "·";
    });
    this.sendBtn.disabled = this.pattern.length === 0;
  }

  _send() {
    this.portal.publish("jam:artist_suggestions", {
      artist_id: localStorage.getItem("vs-client-id") || "artista",
      suggestion: { type: "note_pattern", notes: [...this.pattern],
                    steps: STEPS, duration: "eighth" },
    });
    this.status.textContent = "Patrón enviado — entrando al secuenciador…";
  }

  /* jam:artist_suggestions (rebroadcast): informa si la IA lo cuantizó */
  renderSuggestion(payload) {
    const sug = payload?.suggestion || {};
    const changes = sug.changes || [];
    const who = payload.artist_id === (localStorage.getItem("vs-client-id") || "")
      ? "Tu patrón" : `Patrón de ${payload.artist_id}`;
    this.status.textContent = changes.length
      ? `${who} sonaba fuera de escala: ajustado (${changes.map(c => `${c.from}→${c.to}`).join(", ")}).`
      : `${who} ya está sonando en toda la sala.`;
  }

  /* jam:state: escala vigente + flash del pad que suena */
  renderState(s) {
    if (s.scale !== this.scale || s.root_note !== this.root) {
      this.scale = s.scale;
      this.root = s.root_note || this.root;
      this._buildPads();
    }
    const notes = s.current_notes || [];
    const newest = notes[notes.length - 1];
    if (newest !== this._lastFlash) {
      this._lastFlash = newest;
      for (const b of this.pad.children) {
        b.classList.toggle("pad--playing", Number(b.dataset.midi) === newest);
      }
    }
  }
}
