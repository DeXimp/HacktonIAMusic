/* Mini-teoría musical del cliente (espejo de bridge/music_engine.py).
   Solo lo que la UI necesita: clases de altura de la escala y nombres. */

export const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

const INTERVALS = {
  major: [0, 2, 4, 5, 7, 9, 11],
  minor: [0, 2, 3, 5, 7, 8, 10],
  minor_pentatonic: [0, 3, 5, 7, 10],
  major_pentatonic: [0, 2, 4, 7, 9],
  dorian: [0, 2, 3, 5, 7, 9, 10],
  mixolydian: [0, 2, 4, 5, 7, 9, 10],
  lydian: [0, 2, 4, 6, 7, 9, 11],
  phrygian: [0, 1, 3, 5, 7, 8, 10],
  blues: [0, 3, 5, 6, 7, 10],
  harmonic_minor: [0, 2, 3, 5, 7, 8, 11],
};

const FLATS = { Db: "C#", Eb: "D#", Gb: "F#", Ab: "G#", Bb: "A#" };

export function parseScale(name) {
  const m = /^([A-G])([#b]?)(m?)_([a-z_]+)$/.exec((name || "").trim());
  if (!m) return null;
  let pcName = m[1] + m[2];
  pcName = FLATS[pcName] || pcName;
  const rootPc = NOTE_NAMES.indexOf(pcName);
  let mode = m[4];
  if (mode === "pentatonic") mode = m[3] ? "minor_pentatonic" : "major_pentatonic";
  if (rootPc < 0 || !INTERVALS[mode]) return null;
  return { rootPc, mode };
}

export function pitchClasses(name) {
  const p = parseScale(name);
  if (!p) return new Set();
  return new Set(INTERVALS[p.mode].map((i) => (p.rootPc + i) % 12));
}

export function noteName(midi) {
  return NOTE_NAMES[((midi % 12) + 12) % 12] + (Math.floor(midi / 12) - 1);
}

export function prettyScale(name) {
  const p = parseScale(name);
  if (!p) return name || "—";
  const mood = {
    major: "mayor", minor: "menor", minor_pentatonic: "pent. menor",
    major_pentatonic: "pent. mayor", dorian: "dórico", mixolydian: "mixolidio",
    lydian: "lidio", phrygian: "frigio", blues: "blues",
    harmonic_minor: "menor armónica",
  }[p.mode];
  return `${NOTE_NAMES[p.rootPc]} ${mood}`;
}

/* Opciones de votación de la audiencia (con carácter, no solo nombre). */
export const SCALE_OPTIONS = [
  { id: "Am_pentatonic", mood: "hipnótica y segura" },
  { id: "C_major", mood: "luminosa y abierta" },
  { id: "E_minor", mood: "melancólica" },
  { id: "D_dorian", mood: "groove modal" },
  { id: "G_mixolydian", mood: "rock solar" },
  { id: "Am_blues", mood: "sucia y expresiva" },
];
