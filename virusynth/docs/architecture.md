# Arquitectura — dos loops desacoplados

> Regla cardinal: **el LLM nunca está en el audio path**. Audio local <20 ms;
> colaboración e IA en un loop asíncrono tolerante a segundos.

```mermaid
flowchart TB
    subgraph L1["LOOP 1 · AUDIO REALTIME (&lt;20 ms, solo loopback)"]
        ESP[Arduino UNO — principal<br/>o ESP32 pausado<br/>MPU6050 + FSR + pot + botones] -->|Serial USB 115200<br/>CSV 50 Hz| HW[hardware_link<br/>fallback automático a mock]
        HW --> SR[serial_reader<br/>hilo dedicado]
        SR --> MAP[mapping.py<br/>sensores→música]
        SEQ[sequencer.py<br/>corcheas al BPM] --> OSC
        MAP -->|/pd/set/* /pd/trigger/note| OSC[osc_handler]
        OSC -->|UDP :9000| PD[Pure Data main.pd<br/>synth + FX]
        PD --> DAC((🔊))
    end
    subgraph L2["LOOP 2 · COLABORACIÓN + IA (1–5 s de tolerancia)"]
        PD -.->|/pd/state/* UDP :8000| BR[bridge core<br/>estado global]
        BR <-->|ws://:8765<br/>channels jam:*| WEB[Web App<br/>audiencia · artistas · escenario]
        WEB -.->|jam:state + jam:note_triggered| WA[audio-engine.js<br/>mini-synth Web Audio, opt-in]
        BR -->|snapshot JSON| IA[ai_director<br/>Claude tool use<br/>timeout 5 s]
        IA -->|decisión validada| BR
        IA -.->|fallback| ME[music_engine<br/>reglas locales]
    end
    BR --> SEQ
    BR --> OSC
```

## Presupuesto de latencia (medido/estimado)

| Tramo | Latencia | En el audio path |
|---|---|---|
| Sensor → placa (ADC/I2C @ 50 Hz) | ≤ 20 ms de muestreo | sí |
| Placa → bridge (Serial 115200) | 1–5 ms | sí |
| mapping + OSC loopback | < 1 ms | sí |
| Pd DSP (block 64 @ 44.1 kHz) | 1.5–6 ms | sí |
| **Total gesto → sonido** | **≈ 5–15 ms** | ✅ dentro de <20 ms |
| Web ↔ bridge (WS LAN) | 5–50 ms | no (control) |
| Claude (effort low, tool forzado) | 1.5–5 s, timeout 5 s | no (asíncrono) |

## Reparto de responsabilidades

| Componente | Hace | No hace |
|---|---|---|
| **bridge/** (Python) | cerebro: estado, secuenciador, cuantización, votos, IA, presencia | audio |
| **pd-patches/main.pd** | sintetiza y reporta amplitud | lógica musical, serial, red externa |
| **web/** | UI de 3 roles + orbe | decidir nada (transporte puro) |
| **firmware/** | CSV de sensores 50 Hz (Arduino UNO principal, ESP32 pausado — mismo protocolo) | mapeo musical (vive en el bridge) |
| **Claude** | sugiere mutaciones (JSON validado) | tocar notas, generar audio |

## Cadena de fallbacks (CLAUDE.md §7)

`Claude → reglas locales` · `Portal → WS local` ·
`Hardware desconectado → performer sintético automático (hardware_link.py, ya no requiere --mock-sensors a mano)` ·
`Pd → scripts/test-osc.py` · sin internet → todo lo anterior sigue en pie.
