# pd-patches — main.pd

Un solo patch (menos riesgo en demo). **100% Pure Data Vanilla 0.46+** (probado
en 0.56-2): cero externals — ni mrpeach, ni comport, ni freeverb.

## Flujo de señal

```
bridge (udp 9000)                                   bridge (udp 8000)
      │                                                    ▲
[netreceive -u -b 9000] → [oscparse] → [route ...]         │ [netsend -u -b]
      │ /pd/set/* → [s vs-*]     /pd/trigger/note → [s vs-note]
      ▼
 SYNTH: nota → [mtof] → phasor~ ×2 (detune) + osc~ sub
        → [vcf~] (cutoff = vs-cutoff con rampa 30 ms, Q = vs-res)
        → envolvente pluck ([vline~]: ataque 5 ms, caída 380 ms, vel/127)
 FX:    → drive [*~ 1+dist·8] → [clip~ -0.85 0.85]        (distorsión)
        → [delwrite~/delread4~ 300 ms] con feedback = vs-del·0.65
        → [rev2~] con mezcla wet = vs-rev
 MASTER:→ [*~ vs-vol con rampa 50 ms] → [clip~ -1 1] → [dac~]
 TELEM: [env~] → (dB−40)/60 → /pd/state/amplitude cada 100 ms
        nota disparada → /pd/state/last_note
 BOOT:  [loadbang] → "connect 127.0.0.1 8000" + "; pd dsp 1"
```

## Mensajes que entiende (ver docs/osc-protocol.md)

| Address | Args | Efecto |
|---|---|---|
| `/pd/trigger/note` | int nota, int velocity | dispara la voz |
| `/pd/set/cutoff` | float Hz | filtro `vcf~` (rampa 30 ms) |
| `/pd/set/resonance` | float Q | resonancia del filtro |
| `/pd/set/volume` | float 0–1 | master (rampa 50 ms) |
| `/pd/set/fx/reverb` | float 0–1 | mezcla de reverb |
| `/pd/set/fx/delay` | float 0–1 | nivel+feedback del delay |
| `/pd/set/fx/distortion` | float 0–1 | drive de la distorsión |
| `/pd/set/scale`, `/pd/set/bpm`, `/pd/set/root_note` | — | informativos (el cerebro es el bridge) |

## Probarlo sin bridge

```
python scripts/mock-sensors.py     # arpegio + barridos directo a :9000
```

## Verificación estructural

```
python scripts/validate-pd.py pd-patches/main.pd
```

DSP se activa solo al abrir (`; pd dsp 1`). Si no suena: Media → DSP On,
y revisa el dispositivo de salida en Media → Audio Settings.
