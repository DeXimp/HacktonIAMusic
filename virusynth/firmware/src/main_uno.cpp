/*
 * ViruSynth — firmware Arduino UNO (placa principal)
 *
 * Lee MPU6050 (I2C) + FSR + potenciómetro + 2 botones digitales y emite una
 * trama CSV por Serial USB a 50 Hz:
 *
 *     ax,ay,az,gx,gy,gz,fsr,pot,btn1,btn2\n
 *
 *   ax..az     aceleración en g      (2 decimales, suavizado EMA)
 *   gx..gz     giroscopio en °/s     (1 decimal)
 *   fsr,pot    crudos ADC 10 bits    (0..1023 — ver bridge/config.py:ADC_MAX)
 *   btn1,btn2  0/1 (1 = presionado; INPUT_PULLUP invertido en firmware)
 *
 * El bridge (bridge/serial_reader.py) acepta tramas de 8 O 10 campos: una
 * placa sin botones (p.ej. el ESP32 pausado, ver main_esp32.cpp) sigue
 * funcionando sin tocar el bridge — esa es la abstracción de hardware
 * (CLAUDE.md §2): cualquier placa que hable este CSV es intercambiable.
 * El bridge relayea estos mismos valores hacia Pure Data por OSC usando las
 * direcciones estándar /pd/sensor/pot, /pd/sensor/fsr, /pd/sensor/ax y
 * /pd/trigger/button1 (ver docs/osc-protocol.md) — pd-patches/main.pd ya las
 * procesa hoy con datos simulados, así que conectar esta placa no requiere
 * tocar el patch.
 *
 * Reglas eléctricas (CLAUDE.md / docs/hardware-arduino-uno.md):
 *   - Lógica 5 V (UNO estándar). El MPU6050 en módulo GY-521 se alimenta
 *     de 5V: el módulo regula internamente a 3.3V y ya trae pull-ups I2C en
 *     placa — no hace falta level-shifter externo.
 *   - I2C fijo por hardware en A4 (SDA) / A5 (SCL): no son pines libres.
 *   - ADC de 10 bits (0-1023) fijo por hardware: el UNO NO tiene
 *     analogReadResolution() (eso es solo ESP32/SAMD) — no se llama aquí.
 *   - Botones a GND con INPUT_PULLUP: sin resistencias externas.
 *
 * Presupuesto serial: 10 campos ≈ 40 bytes/trama; a 115200 baud (~11.5 KB/s)
 * se transmiten en ~3.5 ms — muy por debajo de los 20 ms del período de
 * trama, así que Serial.print() nunca bloquea el loop().
 *
 * Arranque resiliente: si el MPU6050 no responde, el LED parpadea rápido y
 * la trama sale igual con imu en 0 — la demo no se cae por un cable suelto.
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// ---------- pines (Arduino UNO) ----------
// I2C (SDA=A4, SCL=A5) es fijo por hardware: Wire.begin() no toma pines.
constexpr int PIN_POT  = A0;       // potenciómetro (cursor)
constexpr int PIN_FSR  = A1;       // sensor de presión (divisor externo a GND)
constexpr int PIN_BTN1 = 2;        // D2, INPUT_PULLUP: gatillo manual (respaldo del FSR)
constexpr int PIN_BTN2 = 3;        // D3, INPUT_PULLUP: botón secundario (uso libre)
constexpr int PIN_LED  = 13;       // LED onboard: lento = OK, rápido = sin MPU

// ---------- temporización ----------
constexpr uint32_t FRAME_INTERVAL_MS = 20;   // 50 Hz, scheduling con millis()
constexpr uint32_t BAUD = 115200;
constexpr float EMA_ALPHA = 0.25f;           // suavizado de la aceleración

Adafruit_MPU6050 mpu;
bool mpuOk = false;

float axF = 0, ayF = 0, azF = 0;             // aceleración filtrada (g)
uint32_t nextFrameAt = 0;
uint32_t ledToggleAt = 0;
bool ledState = false;

void setup() {
  Serial.begin(BAUD);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BTN1, INPUT_PULLUP);
  pinMode(PIN_BTN2, INPUT_PULLUP);
  // ADC: 10 bits (0-1023) es el único modo del UNO — nada que configurar.

  Wire.begin();                    // SDA=A4, SCL=A5 fijos en el UNO
  mpuOk = mpu.begin(0x68, &Wire);
  if (mpuOk) {
    mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
    mpu.setGyroRange(MPU6050_RANGE_250_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_44_HZ);
  }
  // sin Serial.print de arranque: el bridge descarta líneas no numéricas,
  // pero mantener el canal limpio simplifica el debugging con el monitor

  nextFrameAt = millis();
}

void loop() {
  const uint32_t now = millis();

  // LED de estado sin delay(): lento (1 Hz) = todo bien, rápido (5 Hz) = sin MPU
  const uint32_t ledPeriod = mpuOk ? 500 : 100;
  if (now >= ledToggleAt) {
    ledToggleAt = now + ledPeriod;
    ledState = !ledState;
    digitalWrite(PIN_LED, ledState);
  }

  if (now < nextFrameAt) return;                  // scheduling: nada de delay()
  nextFrameAt += FRAME_INTERVAL_MS;
  if (now > nextFrameAt + 5 * FRAME_INTERVAL_MS)  // recupera tras un bloqueo largo
    nextFrameAt = now + FRAME_INTERVAL_MS;

  float ax = 0, ay = 0, az = 0, gx = 0, gy = 0, gz = 0;
  if (mpuOk) {
    sensors_event_t a, g, t;
    if (mpu.getEvent(&a, &g, &t)) {
      // Adafruit entrega m/s² y rad/s → normalizamos a g y °/s (spec de la trama)
      ax = a.acceleration.x / 9.80665f;
      ay = a.acceleration.y / 9.80665f;
      az = a.acceleration.z / 9.80665f;
      gx = g.gyro.x * 57.29578f;
      gy = g.gyro.y * 57.29578f;
      gz = g.gyro.z * 57.29578f;
    } else {
      mpuOk = false;                              // se cayó el I2C: seguir sin IMU
    }
  }

  axF += EMA_ALPHA * (ax - axF);
  ayF += EMA_ALPHA * (ay - ayF);
  azF += EMA_ALPHA * (az - azF);

  const int fsr  = analogRead(PIN_FSR);            // 0..1023
  const int pot  = analogRead(PIN_POT);            // 0..1023
  const int btn1 = digitalRead(PIN_BTN1) == LOW ? 1 : 0;   // INPUT_PULLUP: LOW = presionado
  const int btn2 = digitalRead(PIN_BTN2) == LOW ? 1 : 0;

  // trama CSV de 10 campos — el contrato con bridge/serial_reader.py
  Serial.print(axF, 2); Serial.print(',');
  Serial.print(ayF, 2); Serial.print(',');
  Serial.print(azF, 2); Serial.print(',');
  Serial.print(gx, 1);  Serial.print(',');
  Serial.print(gy, 1);  Serial.print(',');
  Serial.print(gz, 1);  Serial.print(',');
  Serial.print(fsr);    Serial.print(',');
  Serial.print(pot);    Serial.print(',');
  Serial.print(btn1);   Serial.print(',');
  Serial.println(btn2);
}
