# Protocolo OSC — especificación canónica

Fuente de verdad de todos los mensajes OSC. Cualquier mensaje nuevo se
documenta AQUÍ antes de implementarse (CLAUDE.md §6).

## Bridge → Pure Data (control · UDP `localhost:9000`)

| Address | Tipos | Rango | Efecto |
|---|---|---|---|
| `/pd/trigger/note` | i i | nota 0–127, velocity 1–127 | dispara la voz del synth |
| `/pd/set/cutoff` | f | 300–4000 Hz | filtro `vcf~` (rampa 30 ms) |
| `/pd/set/resonance` | f | 0.7–8 | Q del filtro |
| `/pd/set/volume` | f | 0–1 | master (rampa 50 ms) |
| `/pd/set/fx/reverb` | f | 0–1 | mezcla wet de la reverb |
| `/pd/set/fx/delay` | f | 0–1 | nivel + feedback del delay |
| `/pd/set/fx/distortion` | f | 0–1 | drive de la distorsión |
| `/pd/set/scale` | s | p.ej. `Am_pentatonic` | informativo (el bridge cuantiza) |
| `/pd/set/bpm` | i | 60–180 | informativo (el secuenciador vive en el bridge) |
| `/pd/set/root_note` | i | 36–96 | informativo |

## Pure Data → Bridge (telemetría · UDP `localhost:8000`)

| Address | Tipos | Cadencia | Contenido |
|---|---|---|---|
| `/pd/state/amplitude` | f | 10 Hz | envolvente del master: `(env~ dB − 40)/60`, 0–1 |
| `/pd/state/last_note` | i | por nota | eco de la última nota disparada |

## ESP32 → Bridge (Serial USB · no es OSC)

CSV a 50 Hz, 115200 baud: `ax,ay,az,gx,gy,gz,fsr,pot\n`
(aceleración en g ×2 dec · giroscopio en °/s ×1 dec · crudos ADC 0–4095).
El bridge descarta en silencio cualquier línea que no tenga 8 campos numéricos.

## Mapeo sensores → música (bridge/mapping.py)

| Sensor | Parámetro | Mensaje resultante |
|---|---|---|
| accel X (inclinación lateral) | cutoff 300–4000 Hz, curva log | `/pd/set/cutoff` (máx 20 Hz, umbral 2 %) |
| accel Y (inclinación frontal) | índice de nota en la escala (2 octavas) | interno: elige la nota del próximo trigger |
| gyro (magnitud) | delay: base votada ± 0.25 según energía del gesto | `/pd/set/fx/delay` |
| FSR (flanco de subida, umbral 600, histéresis 0.7×) | trigger de nota, velocity 30–127 | `/pd/trigger/note` |
| potenciómetro | volumen master 0–1 | `/pd/set/volume` |

## (Opcional) ESP32 → Bridge por WiFi

Con `-DUSE_WIFI_OSC=1` el firmware emite además `/sensor/frame` (8 floats, el
mismo orden del CSV) por UDP al puerto 9100 del PC. El serial sigue siendo el
camino primario de la demo.
