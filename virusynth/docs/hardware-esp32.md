# Hardware — ESP32 DevKit v1

## Pinout

| Función | GPIO | Notas |
|---|---|---|
| I2C SDA (MPU6050) | 21 | bus a 400 kHz |
| I2C SCL (MPU6050) | 22 | |
| FSR | 34 | ADC1_CH6 · **solo-entrada, sin pull-up interno** → divisor externo obligatorio |
| Potenciómetro (cursor) | 35 | ADC1_CH7 · solo-entrada |
| LED de estado | 2 | onboard: 1 Hz = OK · 5 Hz = MPU6050 ausente |
| (libre para flex) | 32 | ADC1_CH4 si se añade un tercer sensor |

## Reglas eléctricas (no negociables)

1. **Solo ADC1 (GPIO 32–39) para sensores analógicos.** ADC2 queda inutilizable
   con WiFi activo — respetando esto, el modo `USE_WIFI_OSC` nunca rompe nada.
2. **Lógica 3.3 V.** Nada de 5 V a un GPIO. El MPU6050 se alimenta de 3V3
   (los módulos GY-521 llevan regulador, pero alimentarlos de 3V3 es lo seguro).
3. ADC de **12 bits (0–4095)** con atenuación 11 dB (~0–3.1 V útiles) — ya lo
   configura el firmware (`analogReadResolution(12)` + `ADC_11db`).

## Cableado

```
MPU6050:  VCC→3V3   GND→GND   SDA→GPIO21   SCL→GPIO22

FSR (divisor):        3V3 ── FSR ──┬── GPIO34
                                   └── R 10 kΩ ── GND
     (sin presión ≈ 0 · presión fuerte → sube hacia 4095)

Potenciómetro 10 kΩ:  extremo A→3V3   extremo B→GND   cursor→GPIO35
```

## Bring-up (checklist de 5 minutos)

1. `pio run -t upload` dentro de `firmware/` (o Arduino IDE con el core esp32
   y las librerías Adafruit MPU6050 + Unified Sensor).
2. `pio device monitor` → deben verse líneas CSV de 8 campos a 50 Hz.
3. LED a 1 Hz = MPU detectado. A 5 Hz = revisar SDA/SCL/VCC (la trama sigue
   saliendo con imu en 0 — la demo no se cae).
4. Anotar el puerto (p. ej. `COM7`) → `.env` → `SERIAL_PORT=COM7`.
5. `python -m bridge.main --serial-port COM7` → el log debe decir
   `ESP32 conectado en COM7 @ 115200`.

## Troubleshooting

| Síntoma | Causa probable | Arreglo |
|---|---|---|
| `Sin ESP32 en COMx` en el bridge | puerto equivocado u ocupado | ver en el Administrador de dispositivos; cerrar el monitor serie de PlatformIO/Arduino (solo un proceso puede abrir el COM) |
| Trama congelada | cable USB solo-carga | usar cable de datos |
| FSR siempre 0 | falta el divisor a GND | revisar la resistencia de 10 kΩ |
| FSR clavado en 4095 | divisor invertido | el FSR va al 3V3, la resistencia a GND |
| IMU con drift | superficie vibrando | el EMA del firmware ya suaviza; subir `EMA_ALPHA` la hace más reactiva |
| Notas dobles al presionar | rebote del FSR | subir `FSR_TRIGGER_THRESHOLD` en `bridge/config.py` (la histéresis ya está en `mapping.py`) |
