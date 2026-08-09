/*
 * ViruSynth — firmware ESP32 (Fase 4)
 *
 * Lee MPU6050 (I2C) + FSR + potenciómetro y emite una trama CSV por
 * Serial USB a 50 Hz:
 *
 *     ax,ay,az,gx,gy,gz,fsr,pot\n
 *
 *   ax..az  aceleración en g      (2 decimales, suavizado EMA)
 *   gx..gz  giroscopio en °/s     (1 decimal)
 *   fsr,pot crudos ADC 12 bits    (0..4095)
 *
 * Reglas eléctricas (CLAUDE.md / docs/hardware-esp32.md):
 *   - Sensores analógicos SOLO en ADC1 (GPIO 32-39): ADC2 muere con WiFi.
 *   - GPIO 34-39 son solo-entrada y sin pull-ups: el FSR usa divisor externo
 *     de 10 kΩ a GND.
 *   - Lógica 3.3 V. MPU6050 alimentado desde 3V3.
 *
 * Arranque resiliente: si el MPU6050 no responde, el LED parpadea rápido y
 * la trama sale igual con imu en 0 — la demo no se cae por un cable suelto.
 *
 * Modo opcional WiFi-OSC (bonus, demo-first lo deja apagado): compilar con
 * -DUSE_WIFI_OSC=1 y el ESP32 envía /sensor/frame por UDP además del serial.
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

#ifndef USE_WIFI_OSC
#define USE_WIFI_OSC 0
#endif

// ---------- pines (ESP32 DevKit v1) ----------
constexpr int PIN_SDA = 21;        // I2C MPU6050
constexpr int PIN_SCL = 22;
constexpr int PIN_FSR = 34;        // ADC1_CH6, solo-entrada, divisor 10k a GND
constexpr int PIN_POT = 35;        // ADC1_CH7, solo-entrada
constexpr int PIN_LED = 2;         // LED onboard: lento = OK, rápido = sin MPU

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

#if USE_WIFI_OSC
#include <WiFi.h>
#include <WiFiUdp.h>
const char *WIFI_SSID = "CAMBIAME";
const char *WIFI_PASS = "CAMBIAME";
const char *OSC_HOST = "192.168.1.100";      // IP del PC con el bridge
constexpr uint16_t OSC_PORT = 9100;          // puerto OSC WiFi del bridge
WiFiUDP udp;

// Mini codificador OSC (address + ",ffffffff" + 8 float32 big-endian)
size_t oscPad(uint8_t *buf, size_t n) {
  while (n % 4 != 0) buf[n++] = 0;
  return n;
}
void sendOscFrame(float v[8]) {
  static uint8_t buf[128];
  size_t n = 0;
  const char *addr = "/sensor/frame";
  size_t len = strlen(addr);
  memcpy(buf + n, addr, len); n += len; buf[n++] = 0; n = oscPad(buf, n);
  const char *tags = ",ffffffff";
  len = strlen(tags);
  memcpy(buf + n, tags, len); n += len; buf[n++] = 0; n = oscPad(buf, n);
  for (int i = 0; i < 8; i++) {
    uint32_t bits;
    memcpy(&bits, &v[i], 4);
    buf[n++] = bits >> 24; buf[n++] = bits >> 16; buf[n++] = bits >> 8; buf[n++] = bits;
  }
  udp.beginPacket(OSC_HOST, OSC_PORT);
  udp.write(buf, n);
  udp.endPacket();
}
#endif

void setup() {
  Serial.begin(BAUD);
  pinMode(PIN_LED, OUTPUT);

  analogReadResolution(12);                       // 0..4095
  analogSetPinAttenuation(PIN_FSR, ADC_11db);     // rango útil ~0-3.1 V
  analogSetPinAttenuation(PIN_POT, ADC_11db);

  Wire.begin(PIN_SDA, PIN_SCL, 400000);
  mpuOk = mpu.begin(0x68, &Wire);
  if (mpuOk) {
    mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
    mpu.setGyroRange(MPU6050_RANGE_250_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_44_HZ);
  }
  // sin Serial.print de arranque: el bridge descarta líneas no numéricas,
  // pero mantener el canal limpio simplifica el debugging con el monitor

#if USE_WIFI_OSC
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);               // no bloqueante: se envía cuando conecte
#endif

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

  const int fsr = analogRead(PIN_FSR);
  const int pot = analogRead(PIN_POT);

  // trama CSV de 8 campos — el contrato con bridge/serial_reader.py
  Serial.print(axF, 2); Serial.print(',');
  Serial.print(ayF, 2); Serial.print(',');
  Serial.print(azF, 2); Serial.print(',');
  Serial.print(gx, 1);  Serial.print(',');
  Serial.print(gy, 1);  Serial.print(',');
  Serial.print(gz, 1);  Serial.print(',');
  Serial.print(fsr);    Serial.print(',');
  Serial.println(pot);

#if USE_WIFI_OSC
  if (WiFi.status() == WL_CONNECTED) {
    float v[8] = {axF, ayF, azF, gx, gy, gz, (float)fsr, (float)pot};
    sendOscFrame(v);
  }
#endif
}
