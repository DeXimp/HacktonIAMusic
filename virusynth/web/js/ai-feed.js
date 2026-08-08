/* Feed en vivo del Director IA (canal jam:ai_director). */

import { prettyScale } from "./music.js";

const ACTION_LABEL = {
  change_scale: "cambio de escala",
  set_bpm: "tempo",
  set_fx: "efectos",
  harmonic_resolution: "resolución armónica",
  no_change: "mantiene el groove",
};

function formatValue(d) {
  const v = d.value;
  if (d.action === "change_scale") return prettyScale(v);
  if (d.action === "set_bpm") return `${v} BPM`;
  if (d.action === "set_fx" && v && typeof v === "object") {
    return Object.entries(v).map(([k, x]) => `${k} ${Number(x).toFixed(2)}`).join(" · ");
  }
  if (d.action === "harmonic_resolution") {
    const hr = d.harmonic_resolution || {};
    const from = (hr.original_notes || []).join(" ");
    const to = (hr.resolved_notes || []).join(" ");
    return from && to ? `${from} → ${to}` : "";
  }
  return "";
}

export class AIFeed {
  constructor({ onDecision } = {}) {
    this.list = document.getElementById("ai-feed");
    this.sub = document.getElementById("ai-sub");
    this.onDecision = onDecision;
    this.empty = document.createElement("li");
    this.empty.className = "ai-empty";
    this.empty.textContent = "El director está escuchando la sala…";
    this.list.append(this.empty);
  }

  push(d) {
    if (!d || !d.action) return;
    this.empty.remove();
    const li = document.createElement("li");
    li.className = "ai-card";
    const value = formatValue(d);
    const src = d.source === "claude" ? "claude" : "reglas locales";
    li.innerHTML = `
      <div class="ai-card-head">
        <span class="ai-action"></span>
        <span class="ai-value mono"></span>
        <span class="ai-src ${d.source === "claude" ? "ai-src--claude" : ""}"></span>
      </div>
      <p class="ai-reason"></p>`;
    li.querySelector(".ai-action").textContent = ACTION_LABEL[d.action] || d.action;
    li.querySelector(".ai-value").textContent = value;
    li.querySelector(".ai-src").textContent = src;
    li.querySelector(".ai-reason").textContent = d.reasoning || "";
    this.list.prepend(li);
    while (this.list.children.length > 12) this.list.lastChild.remove();
    const hora = new Date().toLocaleTimeString("es-PE", { hour12: false });
    this.sub.textContent = `última decisión ${hora}`;
    if (this.onDecision) this.onDecision(d);
  }
}
