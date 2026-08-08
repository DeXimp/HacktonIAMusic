/* Panel de audiencia: votos de escala, tempo y FX (canal jam:votes:cast). */

import { SCALE_OPTIONS, prettyScale } from "./music.js";
import { throttle } from "./portal-client.js";

export class AudienceUI {
  constructor(portal) {
    this.portal = portal;
    this.myScale = null;
    this.grid = document.getElementById("scale-grid");
    this._buildScaleCards();
    this._wireBpm();
    this._wireFx();
  }

  _buildScaleCards() {
    for (const opt of SCALE_OPTIONS) {
      const card = document.createElement("button");
      card.className = "scale-card";
      card.dataset.scale = opt.id;
      card.innerHTML = `
        <span class="sc-name mono"></span>
        <span class="sc-mood"></span>
        <span class="sc-bar"><span class="sc-fill"></span></span>`;
      card.querySelector(".sc-name").textContent = prettyScale(opt.id);
      card.querySelector(".sc-mood").textContent = opt.mood;
      card.addEventListener("click", () => {
        this.myScale = opt.id;
        for (const c of this.grid.children) c.dataset.mine = c === card ? "1" : "0";
        this.portal.publish("jam:votes:cast", { scale: opt.id });
      });
      this.grid.append(card);
    }
  }

  _wireBpm() {
    const slider = document.getElementById("bpm-slider");
    const label = document.getElementById("bpm-vote-label");
    const publish = throttle((v) => this.portal.publish("jam:votes:cast", { bpm: v }), 250);
    slider.addEventListener("input", () => {
      label.textContent = slider.value;
      publish(Number(slider.value));
    });
  }

  _wireFx() {
    for (const name of ["reverb", "delay", "distortion"]) {
      const slider = document.getElementById(`fx-${name}`);
      const val = document.getElementById(`fx-${name}-val`);
      const publish = throttle(
        (v) => this.portal.publish("jam:votes:cast", { fx: { [name]: v } }), 200);
      slider.addEventListener("input", () => {
        val.textContent = Number(slider.value).toFixed(2);
        publish(Number(slider.value));
      });
    }
  }

  /* jam:votes — agregados de toda la sala */
  renderVotes(v) {
    if (!v) return;
    const votes = v.scale_votes || {};
    const max = Math.max(1, ...Object.values(votes));
    for (const card of this.grid.children) {
      const n = votes[card.dataset.scale] || 0;
      card.querySelector(".sc-fill").style.width = `${(n / max) * 100}%`;
    }
    document.getElementById("bpm-avg").textContent = v.bpm_avg ?? "—";
  }

  /* jam:state — marca la escala sonando ahora */
  renderState(s) {
    for (const card of this.grid.children) {
      card.dataset.live = card.dataset.scale === s.scale ? "1" : "0";
    }
  }
}
