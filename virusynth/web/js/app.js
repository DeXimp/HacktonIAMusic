/* Bootstrap de ViruSynth: rol → conexión realtime → módulos de UI. */

import { Portal } from "./portal-client.js";
import { Visualizer } from "./visualizer.js";
import { AIFeed } from "./ai-feed.js";
import { AudienceUI } from "./audience-ui.js";
import { ArtistUI } from "./artist-ui.js";
import { prettyScale } from "./music.js";

const gate = document.getElementById("role-gate");
const app = document.getElementById("app");

let gateViz = new Visualizer(document.getElementById("gate-canvas"), { idle: true });

function pickRole(role) {
  localStorage.setItem("vs-role", role);
  gateViz?.destroy();
  gateViz = null;
  gate.remove();
  app.hidden = false;
  document.body.dataset.role = role;
  boot(role);
}

const urlRole = new URLSearchParams(location.search).get("role");
if (["audience", "artist", "stage"].includes(urlRole)) {
  pickRole(urlRole);
} else {
  for (const btn of gate.querySelectorAll("[data-pick]")) {
    btn.addEventListener("click", () => pickRole(btn.dataset.pick));
  }
}

function boot(role) {
  const portal = new Portal(role);
  const viz = new Visualizer(document.getElementById("viz"));
  const isStage = role === "stage";

  const caption = document.getElementById("stage-caption");
  const capText = document.getElementById("cap-text");
  const capSource = document.getElementById("cap-source");
  let captionTimer = null;

  const feed = new AIFeed({
    onDecision(d) {
      viz.aiDecision();
      if (isStage && d.reasoning) {
        capSource.textContent = d.source === "claude" ? "IA · claude" : "IA · reglas";
        capText.textContent = d.reasoning;
        caption.hidden = false;
        clearTimeout(captionTimer);
        captionTimer = setTimeout(() => { caption.hidden = true; }, 9000);
      }
    },
  });

  let audience = null, artist = null;
  if (role === "audience") {
    audience = new AudienceUI(portal);
    document.getElementById("audience-panel").hidden = false;
  } else if (role === "artist") {
    artist = new ArtistUI(portal);
    document.getElementById("artist-panel").hidden = false;
  }
  document.getElementById("ai-panel").hidden = false;

  /* ---- badge de conexión ---- */
  const badge = document.getElementById("conn-badge");
  portal.onStatus((s) => {
    if (s === "open") {
      badge.textContent = "en vivo";
      badge.className = "conn conn--on";
    } else {
      badge.textContent = s === "connecting" ? "conectando…" : "sin conexión — reintentando…";
      badge.className = "conn conn--off";
    }
  });

  /* ---- channels jam:* ---- */
  portal.on("jam:state", (s) => {
    viz.setState(s);
    document.getElementById("ro-scale").textContent = prettyScale(s.scale);
    document.getElementById("ro-bpm").textContent = s.bpm ?? "—";
    audience?.renderState(s);
    artist?.renderState(s);
  });
  portal.on("jam:votes", (v) => audience?.renderVotes(v));
  portal.on("jam:ai_director", (d) => feed.push(d));
  portal.on("jam:artist_suggestions", (p) => artist?.renderSuggestion(p));
  portal.on("jam:presence", (p) => {
    document.getElementById("p-perf").textContent = p.performers ?? 0;
    document.getElementById("p-art").textContent = p.artists ?? 0;
    document.getElementById("p-aud").textContent = p.audience ?? 0;
  });

  portal.connect();
}
