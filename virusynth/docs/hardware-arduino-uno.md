# Hardware — Arduino UNO (placa principal)

## Pinout

| Función | Pin | Notas |
|---|---|---|
| I2C SDA (MPU6050) | A4 | fijo por hardware — no reasignable |
| I2C SCL (MPU6050) | A5 | fijo por hardware — no reasignable |
| Potenciómetro (cursor) | A0 | ADC 10 bits, 0–1023 |
| FSR | A1 | ADC 10 bits · divisor externo a GND obligatorio |
| Botón 1 | D2 | `INPUT_PULLUP`, sin resistencias externas — presionado = LOW |
| Botón 2 | D3 | `INPUT_PULLUP`, sin resistencias externas — presionado = LOW |
| LED de estado | 13 (onboard) | 1 Hz = OK · 5 Hz = MPU6050 ausente |

> Los botones se leen y viajan en la trama CSV (`btn1`, `btn2`) y en el
> canal OSC `/pd/trigger/button1` que `main.pd` ya sabe interpretar — pero
> **no tienen ninguna acción musical atada en `bridge/mapping.py` todavía**.
> Es una decisión explícita (ver `docs/superpowers/plans/2026-08-08-arduino-uno-hardware-consolidation.md`):
> el equipo prefirió no inventar semántica de performance sin confirmar
> qué debería hacer cada botón en vivo. Es el punto de extensión más obvio
> del sistema — reasignarlos es agregar unas pocas líneas en
> `SensorMapper.process()` (`bridge/mapping.py`).

## Reglas eléctricas (no negociables)

1. **Lógica 5 V** (estándar del UNO). El MPU6050 en módulo GY-521 se
   alimenta de 5V — el módulo regula internamente a 3.3V y ya trae
   pull-ups I2C en la placa, así que no hace falta level-shifter externo
   (así es como el fabricante del módulo espera que se use con un UNO).
2. **ADC de 10 bits (0–1023) fijo por hardware.** El UNO (ATmega328P) NO
   tiene `analogReadResolution()` ni `analogSetPinAttenuation()` — esas son
   funciones exclusivas de ESP32/SAMD. El firmware no las llama; el rango
   0–1023 es automático. El bridge lo sabe vía `bridge/config.py:ADC_MAX`
   (perfil `arduino_uno`, ver `BOARD_PROFILES`).
3. **I2C fijo en A4 (SDA) / A5 (SCL).** A diferencia del ESP32, no son
   pines libres reasignables — `Wire.begin()` no toma argumentos.
4. **Botones a GND con `INPUT_PULLUP`.** Sin resistencias externas: el
   pull-up interno del microcontrolador ya deja el pin en HIGH en reposo.

## Cableado

```
MPU6050 (GY-521):  VCC→5V    GND→GND    SDA→A4    SCL→A5

FSR (divisor):         5V ── FSR ──┬── A1
                                   └── R 10 kΩ ── GND
     (sin presión ≈ 0 · presión fuerte → sube hacia 1023)

Potenciómetro 10 kΩ:  extremo A→5V   extremo B→GND   cursor→A0

Botón 1:  D2 ── botón ── GND   (INPUT_PULLUP interno, sin resistencia)
Botón 2:  D3 ── botón ── GND   (INPUT_PULLUP interno, sin resistencia)
```

## Bring-up (checklist de 5 minutos)

1. `pio run -t upload` dentro de `firmware/` — compila `main_uno.cpp`, que
   es el entorno por defecto (`default_envs = uno` en `platformio.ini`). O
   Arduino IDE con el core AVR estándar y las librerías Adafruit MPU6050 +
   Unified Sensor.
2. `pio device monitor` → deben verse líneas CSV de **10** campos a 50 Hz
   (`ax,ay,az,gx,gy,gz,fsr,pot,btn1,btn2`).
3. LED a 1 Hz = MPU detectado. A 5 Hz = revisar SDA/SCL/VCC (la trama sigue
   saliendo con imu en 0 — la demo no se cae).
4. Anotar el puerto (p. ej. `COM7`) → `.env` → `SERIAL_PORT=COM7`.
   `HARDWARE_BOARD=arduino_uno` es el default, no hace falta ponerlo.
5. `python -m bridge.main --serial-port COM7` → el log debe decir
   `Hardware conectado en COM7 @ 115200`. Si no hay placa conectada, el
   bridge activa el performer sintético automáticamente — no hace falta
   pasar `--mock-sensors` a mano (`bridge/hardware_link.py`).

## Troubleshooting

| Síntoma | Causa probable | Arreglo |
|---|---|---|
| `Sin hardware en COMx` en el bridge | puerto equivocado u ocupado | ver en el Administrador de dispositivos; cerrar el monitor serie de PlatformIO/Arduino (solo un proceso puede abrir el COM) |
| Trama congelada | cable USB solo-carga | usar cable de datos |
| FSR siempre 0 | falta el divisor a GND | revisar la resistencia de 10 kΩ |
| FSR clavado en 1023 | divisor invertido | el FSR va al 5V, la resistencia a GND |
| IMU con drift | superficie vibrando | el EMA del firmware ya suaviza; subir `EMA_ALPHA` la hace más reactiva |
| Notas dobles al presionar | rebote del FSR | subir `FSR_TRIGGER_THRESHOLD` en `bridge/config.py` (la histéresis ya está en `mapping.py`) — el default ya está recalibrado para la escala de 10 bits del UNO |
| Botones no hacen nada | es el comportamiento esperado hoy | ver la nota de arriba — están parseados pero inertes a propósito |
