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
| `/pd/trigger/button1` | — (bang) | — | dispara la voz (gatillo manual, redundante al FSR) |

### Sensores "crudos" (Etapa 2 — preview local / futuro pass-through de hardware)

Rama nueva, en paralelo a la de arriba (no la reemplaza). `main.pd` ya la
procesa hoy con datos simulados (`scripts/mock-sensors.py`); cuando el
Arduino UNO físico esté conectado, el bridge podrá relayear sus lecturas por
estas mismas direcciones sin que el patch cambie. Es acondicionamiento de
señal simple (umbral, escalado) — la cuantización de escala y las
decisiones armónicas reales siguen siendo exclusivas de `bridge/mapping.py`
(CLAUDE.md §2).

| Address | Tipos | Contrato | Efecto en Pd |
|---|---|---|---|
| `/pd/sensor/pot` | f | **normalizado 0–1** (misma convención que `/pd/set/volume`) | volumen master |
| `/pd/sensor/fsr` | f | normalizado 0–1 | cruce de umbral (>0.3) con flanco → dispara nota |
| `/pd/sensor/ax` | f | mismo rango ±g que el CSV | escalado lineal → cutoff 300–4000 Hz |

La normalización de rango crudo del ADC (0–1023 en Arduino UNO, 0–4095 en
ESP32 — ver `bridge/config.py:ADC_MAX`) es responsabilidad de quien envía el
mensaje OSC, nunca de Pd.

## Pure Data → Bridge (telemetría · UDP `localhost:8000`)

| Address | Tipos | Cadencia | Contenido |
|---|---|---|---|
| `/pd/state/amplitude` | f | 10 Hz | envolvente del master: `(env~ dB − 40)/60`, 0–1 |
| `/pd/state/last_note` | i | por nota | eco de la última nota disparada |

## Hardware → Bridge (Serial USB · no es OSC)

CSV a 50 Hz, 115200 baud: `ax,ay,az,gx,gy,gz,fsr,pot[,btn1,btn2]\n`
(aceleración en g ×2 dec · giroscopio en °/s ×1 dec · fsr/pot crudos ADC,
rango según la placa activa — `bridge/config.py:ADC_MAX`: 0–1023 en Arduino
UNO, 10 bits, hardware principal; 0–4095 en ESP32, 12 bits, pausado). El
bridge descarta en silencio cualquier línea que no tenga 8 o 10 campos
numéricos; si son 8 (placa sin botones), rellena `btn1=btn2=0`. Cualquier
placa que hable este CSV es intercambiable sin tocar el bridge — cambiar de
hardware es cambiar `HARDWARE_BOARD` (env var).

Arduino UNO agrega `btn1` (D2), `btn2` (D3): 0/1, `INPUT_PULLUP` (1 =
presionado). Se parsean en `bridge/mapping.py` pero no tienen acción
musical atada todavía (punto de extensión, ver `docs/hardware-arduino-uno.md`).

## Mapeo sensores → música (bridge/mapping.py)

| Sensor | Parámetro | Mensaje resultante |
|---|---|---|
| accel X (inclinación lateral) | cutoff 300–4000 Hz, curva log | `/pd/set/cutoff` (máx 20 Hz, umbral 2 %) |
| accel Y (inclinación frontal) | índice de nota en la escala (2 octavas) | interno: elige la nota del próximo trigger |
| gyro (magnitud) | delay: base votada ± 0.25 según energía del gesto | `/pd/set/fx/delay` |
| FSR (flanco de subida, umbral `config.FSR_TRIGGER_THRESHOLD` ≈14.65% del fondo de escala, histéresis 0.7×) | trigger de nota, velocity 30–127 | `/pd/trigger/note` |
| potenciómetro | volumen master 0–1 | `/pd/set/volume` |
| botones D2/D3 (Arduino UNO) | — | sin acción todavía (inertes a propósito) |

## (Opcional) ESP32 → Bridge por WiFi

Con `-DUSE_WIFI_OSC=1` el firmware emite además `/sensor/frame` (8 floats, el
mismo orden del CSV) por UDP al puerto 9100 del PC. El serial sigue siendo el
camino primario de la demo.
