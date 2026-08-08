# Prompt para Deep Research — Estado del Arte y Posicionamiento de **ViruSynth**
### (v2 · 7 de agosto de 2026 — reorienta `prompt_deep_research_ia_fisica_vs_musical_v1.md`, que se conserva como registro del proceso de decisión)

---

## Por qué esta versión existe

La v1 servía para **elegir** entre dos líneas de investigación (L1 "IA interactuando con el mundo físico" vs. L2 "IA colaboradora musical") antes de construir nada. Esa decisión ya se tomó y se ejecutó: **ViruSynth** es un sistema funcional y verificado que no eligió una línea, sino que **las fusionó** — sensores en ESP32 y protocolos de baja latencia (L1) al servicio de un instrumento colaborativo con IA directora (L2), más una tercera dimensión que la v1 no contemplaba: **colaboración multiusuario en tiempo real con audiencia remota**.

Con el sistema construido, la pregunta de investigación cambia de *"¿qué hago?"* a **cuatro preguntas nuevas**:

1. ¿Qué decisiones arquitectónicas de ViruSynth están **respaldadas** por la literatura y cuáles están **refutadas o superadas** por trabajo existente?
2. ¿Qué es **genuinamente nuevo** aquí y qué ya existe (académica, open-source **y comercialmente**)?
3. ¿Qué **hay que medir** para convertir el prototipo en una contribución publicable, y en qué venue?
4. ¿Qué productos, apps y plataformas ya lanzadas ocupan este espacio, con qué modelo de negocio, y cuáles **fracasaron** (evidencia de mercado tan valiosa como la de éxito)?

### Registro de cambios respecto a la v1

| # | Cambio | Motivo |
|---|--------|--------|
| 1 | Objetivo: de *decidir entre 2 líneas* a *posicionar un sistema construido* | La decisión ya se ejecutó; buscar "cuál elijo" ahora es trabajo desperdiciado |
| 2 | Los 10 ítems se reagrupan en **3 líneas** (A: arquitectura y tiempo real · B: colaboración y co-creatividad · C: producto y mercado) y se re-alcanzan a los componentes reales del sistema | Los ítems P02/P04 de la v1 (dashboards, digital twins) quedaron fuera del sistema final; los que sí se construyeron (audiencia participativa, mediación de conflictos, degradación elegante) no existían en la v1 |
| 3 | **Nueva Línea C + nuevo bloque `Panorama_Comercial_Apps_y_Plataformas`** con 20 campos por producto | Pedido explícito: cubrir apps y tecnologías lanzadas en web o como aplicación. La v1 solo miraba papers y repositorios |
| 4 | Spine de **6 afirmaciones verificables (C1–C6)** extraídas del sistema real, con veredicto obligatorio por ítem (`confirma`/`matiza`/`refuta`/`sin_evidencia`) | Sin esto, un estado del arte sobre un sistema ya construido degenera en bibliografía decorativa |
| 5 | Sesgo a vigilar **invertido**: ya no es "cercanía al perfil del investigador" sino **sesgo de confirmación del sistema construido** | Habiendo invertido en ViruSynth, la tentación es buscar literatura que lo valide. El prompt ahora **exige** buscar evidencia que lo refute |
| 6 | Nuevos bloques `Matriz_de_Novedad`, `Ruta_de_Publicacion`, `Vacios_de_Evidencia`, `metadata_ejecucion` | Convierten el entregable en un plan de publicación, no en una lista de lecturas |
| 7 | JSON mejorado: **arrays** en vez de objetos pseudo-numerados, **enums** en campos comparables, **`null`** para lo desconocido (nunca inventar), **IDs estables** con referencias cruzadas, latencias como número + unidad | Hace la salida validable por script (`len(papers) >= 3`) y comparable entre ítems; los strings vacíos de la v1 no distinguían "no aplica" de "no encontrado" |
| 8 | Métricas medidas del sistema real incluidas como referencia de contraste | Permite comparar contra números reportados en literatura en vez de discutir en abstracto |
| 9 | Se admite y **se pide** evidencia de productos discontinuados o adquiridos | Un producto muerto informa sobre el mercado tanto como uno vivo |

---

## Rol / Objetivo

Actúa como un **investigador senior en Computer Music/NIME, sistemas interactivos en tiempo real, HCI/CSCW e IA aplicada**, con dos capacidades adicionales: (a) verificar indexación de literatura científica (Scopus / IEEE Xplore / ACM DL / SpringerLink / ScienceDirect), y (b) **auditar el panorama de productos lanzados** — apps web y nativas, plugins, hardware comercial, SDKs de infraestructura realtime y servicios SaaS — verificando su estado actual (activo / discontinuado / adquirido).

Tu tarea: generar **10 ítems técnicos (P01–P10)** en **3 líneas**, más los bloques transversales especificados, que en conjunto constituyan (i) un Estado del Arte riguroso para posicionar el sistema **ViruSynth**, (ii) un análisis de originalidad frente a la práctica académica **y comercial**, y (iii) una ruta accionable hacia publicación científica.

**No asumas que ViruSynth es novedoso.** Tu trabajo más valioso es encontrar el sistema, paper o producto que ya hizo lo mismo. Si existe, dilo con claridad y explica en qué se diferencia (o si no se diferencia en absoluto).

**La salida final debe ser el objeto JSON especificado en "Formato de salida (obligatorio)". No adelantes conclusiones fuera de ese JSON.**

---

## Contexto: el sistema ya construido

**ViruSynth** — instrumento musical colaborativo en tiempo real con cuatro actores simultáneos, construido y verificado el 7 de agosto de 2026 para el **Realtime Hackathon by Portal** (7–9 ago 2026).

### Arquitectura: dos lazos desacoplados

```
LAZO 1 — AUDIO REALTIME (<20 ms, local, solo loopback)
  ESP32 (MPU6050 + FSR + potenciómetro)
    → Serial USB 115200, trama CSV de 8 campos a 50 Hz
    → Bridge Python (hilo serial dedicado + mapeo sensor→música + secuenciador)
    → OSC/UDP localhost:9000
    → Pure Data vanilla (synth 3 osciladores + vcf~ + distorsión + delay + rev2~)
    → 🔊

LAZO 2 — COLABORACIÓN + IA (1–5 s de tolerancia)
  Pure Data → OSC/UDP :8000 (telemetría de amplitud, 10 Hz) → Bridge
  Bridge ↔ WebSocket :8765 (channels jam:*) ↔ Web App (audiencia · artistas · escenario)
  Bridge → HTTPS → Claude (tool use, timeout duro 5 s) → validación → OSC → Pd
                 ↘ fallback → motor de reglas de teoría musical local
```

### Reparto de responsabilidades

| Componente | Rol | Explícitamente NO hace |
|---|---|---|
| Bridge Python | Cerebro: estado global, secuenciador, cuantización a escala, agregación de votos, orquestación de la IA, presencia | Sintetizar audio |
| Pure Data (vanilla, sin externals) | Síntesis y FX; reporta amplitud real vía `env~` | Lógica musical, red externa, lectura de serial |
| Capa realtime (WS local; adaptador para Portal SDK) | Transporte de mensajes `jam:*` | Decidir nada |
| LLM (Claude) | Sugerir **una** mutación musical por turno, como JSON validado contra esquema | Generar audio, disparar notas directamente |
| ESP32 | CSV de sensores a 50 Hz | Mapeo musical |

### Métricas reales del sistema (contrastar contra lo reportado en literatura)

| Parámetro | Valor medido / configurado |
|---|---|
| Presupuesto gesto → sonido | ≈5–15 ms (muestreo 20 ms + serial 1–5 ms + OSC loopback <1 ms + DSP Pd 1.5–6 ms @ block 64/44.1 kHz) |
| Tasa de sensores | 50 Hz (trama CSV de 8 campos) |
| Telemetría Pd → bridge | 10 Hz |
| Estado global → clientes | 10 Hz · votos agregados 1 Hz |
| Cadencia del Director IA | ~7 s, con **timeout duro de 5 s** → fallback local |
| Gradualidad impuesta a la IA | ≤10 BPM y ≤0.2 en FX por decisión; cooldown de cambio de escala 20 s |
| Aplicación de FX votados | Interpolación 15 % cada 0.5 s hacia el promedio de la sala |
| Verificación ejecutada | 32 tests unitarios del motor musical · round-trip real contra Pd headless · smoke test OSC · prueba de UI en navegador |

### Las 6 afirmaciones a validar (spine del estudio)

Cada ítem P01–P10 debe emitir un veredicto sobre al menos una de estas afirmaciones. **Son hipótesis, no hechos.**

| ID | Afirmación de ViruSynth | Dónde vive en el código |
|---|---|---|
| **C1** | Separar el lazo de audio (local, <20 ms) del lazo de IA (nube, 1–5 s) permite integrar un LLM en performance en vivo sin degradar la sensación instrumental | `bridge/main.py`, `osc_handler.py`, `pd-patches/main.pd` |
| **C2** | El LLM debe operar como **director** (emite parámetros de control validados contra esquema vía tool use), no como generador de audio ni de notas | `ai_director.py`, `music_engine.validate_decision()` |
| **C3** | Un motor de reglas de teoría musical local como fallback ante timeout mantiene coherencia musical y hace la performance independiente de la nube | `music_engine.rule_based_suggestion()` |
| **C4** | Una audiencia remota puede actuar como **instrumentista colectivo** si los parámetros se dividen por política: FX aplicados en caliente, escala/tempo arbitrados por la IA con gradualidad y cooldown | `main.py::_apply_voted_fx`, `state.aggregate_votes()` |
| **C5** | Ante propuestas simultáneas de varios humanos, la IA aporta más valor **mediando conflictos armónicos** (cuantizar, resolver, explicar en lenguaje natural) que componiendo | `music_engine.find_clashes/resolve_pattern`, `_on_artist_suggestion` |
| **C6** | Un microcontrolador de bajo coste (ESP32, CSV serial) + Pure Data **vanilla sin externals**, con la lógica musical fuera de Pd, alcanza el presupuesto de latencia con máxima portabilidad | `firmware/src/main.cpp`, `serial_reader.py`, `mapping.py` |

### Contexto del investigador y del taller (sin cambios respecto a v1)

- **Investigador**: ingeniero electricista-electrónico (UNI-FIEE); experiencia en telecomunicaciones, RF, microondas, redes de formación de haz. Sin formación previa específica en HCI, physical computing musical ni NIME.
- **Taller de referencia**: *"Microcontroladores, música y arte sonoro: integración entre Arduino y Pure Data"*, dictado por el **Dr. Jaime Oliver La Rosa** (NYU; co-director de los NYU Waverly Labs for Computing and Music; PhD en Computer Music por UC San Diego bajo Miller Puckette, creador de Pure Data). Línea relevante: instrumentos que "escuchan, entienden, recuerdan y responden"; controladores open-source **Silent Drum** y **MANO** (visión por computador para gesto de la mano).
- **Evento**: Realtime Hackathon by Portal, 39 h, 7–9 ago 2026. Requisito: IA + interacción realtime multiusuario vía Portal.
  > ⚠️ **Verificar antes de usar**: qué es exactamente **Portal** como producto (SDK realtime, pub/sub, presence), su documentación pública, su modelo de negocio y su posición frente a Ably/PubNub/Liveblocks/PartyKit. Es a la vez el patrocinador del evento y un competidor directo en la Línea C.

---

## Estructura de los 10 ítems

### Línea A — Arquitectura y tiempo real (P01–P04) · afirmaciones C1, C2, C3, C6

- **P01** — Desacoplamiento IA/audio: arquitecturas de dos (o más) lazos con presupuestos de latencia asimétricos; IA como consejera asíncrona fuera del audio path
- **P02** — Microcontroladores de bajo coste como controladores gestuales hacia un host de síntesis: Serial/Firmata vs. OSC-sobre-WiFi vs. BLE-MIDI; jitter, fiabilidad y coste de arranque
- **P03** — LLMs y agentes como **controladores de parámetros** musicales: tool use / salida estructurada / validación de esquema; latencia de inferencia y estrategias de acotación
- **P04** — Resiliencia y degradación elegante en sistemas de performance en vivo: fallbacks deterministas, timeouts, tolerancia a fallos de red y diseño para el fallo en escena

### Línea B — Colaboración multiusuario y co-creatividad (P05–P08) · afirmaciones C4, C5

- **P05** — Audiencia participativa / *crowd-in-the-loop* en música en vivo: agregación de intención colectiva, escala, latencia tolerable, diseño de agencia percibida
- **P06** — Networked Music Performance y sincronización de estado distribuido: umbrales de latencia, relojes, presencia, CRDT/state sync en la web
- **P07** — IA como **mediadora** de conflictos creativos entre múltiples humanos: iniciativa mixta, arbitraje, explicabilidad de la decisión creativa
- **P08** — Evaluación de co-creatividad y agencia compartida: instrumentos validados, protocolos de estudio con músicos y con audiencia, métricas reportables en un paper

### Línea C — Producto, mercado y tecnología lanzada (P09–P10) · transversal a todas las afirmaciones

- **P09** — **Productos, apps y plataformas ya lanzadas** de creación musical colaborativa y/o asistida por IA: web apps, apps móviles/desktop, plugins DAW, hardware comercial. Estado, adopción, modelo de negocio, y **qué se discontinuó y por qué**
- **P10** — Infraestructura realtime comercial (Portal, Ably, PubNub, Liveblocks, PartyKit, Cloudflare Durable Objects/Calls…) y modelos de negocio para experiencias interactivas en vivo: pricing, límites de latencia/escala declarados, viabilidad de un SaaS por sesión o por evento

Si algún ítem carece de sustento suficiente, **sustitúyelo por una variante equivalente dentro de la misma línea** y deja constancia en `desafios_abiertos` y en `Vacios_de_Evidencia`.

---

## Preguntas de investigación por línea

### Línea A — Arquitectura y tiempo real

- ¿Qué sistemas documentados ubican explícitamente a un modelo generativo o LLM **fuera** del audio path, y cómo justifican el reparto de latencias? ¿Existe una taxonomía publicada de "IA en el lazo" vs. "IA sobre el lazo" para música interactiva?
- Umbrales de latencia reportados: ¿qué evidencia empírica sustenta el clásico <10–20 ms para sensación instrumental, y los ~25–30 ms como techo de la performance remota síncrona? ¿Hay estudios que midan el umbral por tipo de gesto o instrumento?
- ESP32/Arduino → host: latencia y jitter **medidos** por protocolo (Serial/USB-CDC, OSC sobre WiFi, BLE-MIDI, USB-MIDI). ¿Qué reporta la literatura NIME sobre la penalización real del WiFi frente al cable en escena?
- Comparación con plataformas embebidas de audio de baja latencia (**Bela**, Daisy Seed, Norns, Zynthian): ¿qué gana o pierde una arquitectura que deja el DSP en un PC frente a una que lo embebe?
- LLMs con salida estructurada como controladores: latencias de inferencia reportadas, tasas de salida inválida frente a esquema, y estrategias documentadas de acotación (timeout, presupuesto de tokens, esfuerzo de razonamiento, caché).
- Ingeniería de resiliencia: ¿qué documenta la literatura de instalaciones de arte y performance sobre modos de fallo en escena y estrategias de degradación? ¿Existen patrones publicados (no solo folklore de practicantes)?
- **Alternativa que ViruSynth no tomó**: síntesis neural en tiempo real dentro de Pd/Max (**RAVE + `nn~`** de IRCAM/ACIDS, Neutone, DDSP-VST). ¿Qué latencia y qué coste computacional reportan, y en qué escenario superarían al enfoque "LLM como director de un synth clásico"?

### Línea B — Colaboración multiusuario y co-creatividad

- Sistemas documentados de participación de audiencia en música en vivo (linaje que incluye trabajos tipo *Open Symphony*, *massMobile*, *Fantom*, orquestas de smartphones): ¿cómo agregan la intención colectiva (votación, promedio, muestreo, consenso), y qué reportan sobre la **agencia percibida** cuando N es grande?
- ¿Qué evidencia hay sobre el reparto de control entre performer y audiencia — qué parámetros conviene ceder a la multitud y cuáles no? ¿Alguien ha reportado la distinción "parámetros continuos aplicados en caliente vs. parámetros estructurales arbitrados"?
- Networked Music Performance: arquitecturas de sincronización de estado (relojes, buffers adaptativos, CRDT, autoridad centralizada) y sus umbrales; ¿qué se aplica cuando lo que viaja es **control** y no audio?
- IA de iniciativa mixta como árbitro entre humanos: ¿hay trabajo publicado donde el sistema **resuelve conflictos** entre aportes creativos simultáneos en vez de generar contenido propio? ¿Cómo se evalúa la legitimidad percibida de esa mediación?
- Explicabilidad creativa: ¿qué se sabe sobre mostrar el "razonamiento" de la IA a la audiencia en vivo (ViruSynth publica un `reasoning` en lenguaje natural en cada decisión)? ¿Mejora la aceptación o distrae?
- Métricas e instrumentos validados aplicables: Creativity Support Index, escalas de *sense of agency*, NASA-TLX, cuestionarios de engagement musical, protocolos Wizard-of-Oz. ¿Cuáles son estándar en NIME/CHI para un sistema como este, y con cuántos participantes?

### Línea C — Producto, mercado y tecnología lanzada

> Esta línea es **obligatoriamente empírica sobre el estado actual del mercado**, no bibliográfica. Verifica cada producto en su fuente primaria.

- ¿Qué productos permiten hoy **crear música en colaboración en tiempo real** (web o app)? Registrar latencia declarada, modelo de sincronización (audio real vs. control/loops), plataformas, precio.
- ¿Qué productos ponen **IA generativa** en el flujo musical, y en qué punto del flujo (generación completa de pistas vs. asistencia paramétrica vs. síntesis neural en el instrumento)?
- ¿Existe **algún producto comercial con un rol de "director/árbitro de IA"** sobre una sesión musical multiusuario? Si no existe, decláralo explícitamente: es el hueco central de la propuesta de valor de ViruSynth.
- ¿Qué productos de **interacción con audiencia** existen en el ecosistema de eventos en vivo y streaming, y cuáles llegan a afectar el contenido artístico (no solo encuestas y engagement)?
- ¿Qué hardware comercial de **instrumentos con sensores** compite con el ESP32+IMU+FSR (Mi.Mu Gloves, Genki Wave, Instruments of Things SOMI-1, Artiphon, Enhancia Neova)? Precio, latencia declarada, protocolo.
- **Productos discontinuados o adquiridos**: identifícalos y registra la causa declarada o inferida (falta de mercado, coste de infraestructura, adquisición, pivote). Un cementerio bien documentado es evidencia de primera para la sección de riesgos.
- Infraestructura realtime: pricing por conexión/mensaje, límites de latencia y de escala declarados, y qué implicaría económicamente una sesión de ViruSynth con 50, 500 o 5000 espectadores simultáneos.

### Transversal a todos los ítems

- Conexión explícita con la línea del **Dr. Jaime Oliver La Rosa** (Silent Drum, MANO, Pure Data) cuando aplique.
- Para cada ítem: **veredicto** sobre las afirmaciones C1–C6 que toque, y **qué habría que medir en ViruSynth** para sostener o refutar esa afirmación con datos propios.

---

## Cobertura obligatoria de productos, apps y tecnologías lanzadas

Esta sección responde al requisito de cubrir **tecnología efectivamente lanzada**, no solo literatura.

### Qué cuenta como "producto" para este estudio

Web app · app móvil (iOS/Android) · app de escritorio · plugin de DAW (VST3/AU/AAX) · external o librería para Pd/Max · hardware comercial · SDK o servicio de infraestructura · extensión de plataforma de streaming · proyecto open-source con usuarios reales y releases.

### Dónde buscar

| Categoría | Fuentes |
|---|---|
| Descubrimiento de producto | Product Hunt, Hacker News (*Show HN*), Devpost (ediciones previas del propio Realtime Hackathon), GitHub trending y topics (`music-collaboration`, `web-audio`, `nime`, `live-coding`) |
| Tiendas de aplicaciones | App Store y Google Play (categoría Música): fecha de lanzamiento, **fecha de última actualización**, versión, reseñas |
| Mercado e industria | Crunchbase, G2/Capterra, MIDiA Research, Water & Music, Music Ally |
| Prensa especializada | CDM (createdigitalmusic.com), MusicTech, MusicRadar, Synthtopia, Ask.Audio, Attack Magazine |
| Comunidad técnica musical | IRCAM Forum, Cycling '74, foros de Pure Data, Bela.io, Monome/lines, Elektronauts |
| Hardware | NAMM, Superbooth, Knobcon, Ableton Loop (anuncios y demos) |
| Infraestructura realtime | Blogs y docs de Portal, Ably, PubNub, Liveblocks, PartyKit, Cloudflare (Durable Objects / Calls), Colyseus, Yjs |

### Semillas de vocabulario — **verificar todas antes de incluir**

Estos nombres orientan la búsqueda; **no son un listado verificado**. Confirma existencia, estado actual y fecha de cada uno; varios pueden haber sido discontinuados, adquiridos o pivotado.

- **Colaboración musical**: BandLab, Endlesss, Soundtrap, Splice, Sessionwire, JamKazam, Jamulus, SonoBus, Audiomovers Listento, OpenStudio
- **IA musical generativa**: Suno, Udio, Stable Audio, AIVA, Boomy, MusicGen, ElevenLabs Music, Google Magenta (incl. variantes realtime)
- **IA en el instrumento (no generación de pistas)**: IRCAM ACIDS **RAVE + `nn~`** (external para Pd y Max — el vecino más cercano dentro del propio ecosistema de Pure Data), Neutone, DDSP-VST
- **Live coding y música colaborativa en navegador**: Strudel, Estuary, Flok, Gibber, Sonic Pi
- **Instrumentos con sensores**: Mi.Mu Gloves, Genki Wave, Instruments of Things SOMI-1, Artiphon (Orba/Chorda), Enhancia Neova, ROLI
- **Embebido de baja latencia**: Bela, Daisy Seed, Norns, Organelle, Zynthian
- **Audiencia y streaming interactivo**: Uplause, extensiones de Twitch, Stationhead, Turntable, plataformas de polling en vivo
- **Infraestructura realtime**: **Portal** (patrocinador — caracterizar como producto), Ably, PubNub, Liveblocks, PartyKit, Cloudflare Durable Objects/Calls, Colyseus, Yjs

### Qué registrar de cada producto

Los 20 campos del bloque `Panorama_Comercial_Apps_y_Plataformas` (ver esquema JSON). Tres son obligatorios y suelen omitirse: **`estado`** (activo/discontinuado/adquirido), **`ultima_actividad_verificada`** (fecha comprobada, no supuesta) y **`amenaza_para_la_originalidad`** (alta/media/baja, con justificación).

---

## Restricciones del sistema real (sustituyen a "condiciones de factibilidad" de la v1)

- Toda recomendación debe ser implementable sobre la base ya construida: Python 3.11+, Pure Data **vanilla** (sin externals), ESP32 con Arduino/PlatformIO, web vanilla sin CDNs, y una API de LLM comercial. Señala explícitamente cuando una alternativa exigiría romper alguna de estas restricciones (p. ej. `nn~` obliga a introducir un external en Pd — es una decisión legítima, pero debe declararse como tal).
- Distingue siempre entre lo que requeriría **entrenar o afinar un modelo** (alto coste, fuera del alcance actual) y lo que se resuelve con modelos preentrenados vía API/prompting/agentes.
- Prioriza propuestas **validables por software** (patch de Pd, script Python, mock de API, simulación) antes de exigir hardware adicional o estudios de usuario presenciales.
- Para cada métrica sugerida, indica el **instrumento de medida concreto** (p. ej. "loopback de audio con micrófono y análisis de onset en Audacity/Python" para latencia gesto→sonido; no "medir la latencia").

## Requisitos de las fuentes

- **Académicas**, en este orden: Scopus, IEEE Xplore, ACM Digital Library, SpringerLink, ScienceDirect, Google Scholar. Priorizar **Q1/Q2** (SJR/JCR) en revistas; para conferencias (**NIME, CHI, CSCW, ISMIR, ICMC, SMC, Audio Mostly, UIST, TEI, DIS, ACM Multimedia, AES**) usar **CORE (A\*/A)** o el reconocimiento como venue de referencia del subcampo; registrar el ranking o su ausencia como dato informativo, sin excluir por ello.
- **Ventana temporal**: 2020–2026. Excepciones fundacionales anteriores van en `Fuentes_Fundacionales`.
- **Preprints** (arXiv: cs.SD, cs.HC, cs.MA, eess.AS): admitidos si se señalan como tales.
- **Fuentes de producto**: se admiten y se requieren fuentes no académicas (documentación oficial, changelog, tienda de apps, prensa especializada, repositorio). **Cada producto debe tener una `fuente_de_verificacion` primaria**, no un artículo de blog que lo mencione de pasada.
- **Idioma**: inglés para lo técnico; español admitido para contexto institucional peruano (UNI, INICTEL-UNI, eventos locales).
- Cada paper debe respaldar explícitamente al menos uno de: (a) motivación/caso de uso, (b) marco teórico o arquitectura de referencia, (c) viabilidad técnica/experimental o evaluación de usuario, (d) **método de evaluación reutilizable** para el eventual estudio de ViruSynth.

## Calidad, cobertura y sesgos a vigilar

- Los ítems dentro de cada línea deben ser técnicamente distintos entre sí.
- Sin duplicidad: cada paper se usa una vez con un rol claro; los surveys que abarquen varios ítems deben declararlo en `relacion_con_el_problema`.
- **Sesgo principal a vigilar — confirmación del sistema construido.** Habiendo invertido en ViruSynth, existe una presión real a buscar solo literatura que lo valide. Contrarréstala de forma activa:
  1. Para **cada** afirmación C1–C6, busca deliberadamente evidencia **en contra** antes de buscar evidencia a favor.
  2. Al menos **una** afirmación debe recibir veredicto `matiza` o `refuta` en algún ítem, salvo que puedas justificar explícitamente por qué las seis quedan intactas frente a la literatura.
  3. Si encuentras un sistema o producto que hace lo mismo y mejor, **dilo en `Matriz_de_Novedad` con `nivel_de_novedad: "nulo"`** en vez de matizarlo.
- **Sesgo secundario** — el instructor del taller (Dr. Oliver) es autoridad en la Línea B; su trabajo es relevante, pero no debe sobre-representarse ni cerrar la búsqueda a su enfoque.
- **Balance**: las tres líneas se desarrollan con el mismo rigor. La Línea C es empírica y de campo, pero exige el mismo nivel de verificación que las otras dos.

---

## Formato de salida (obligatorio)

Devuelve **exclusivamente** un único objeto JSON válido con esta forma. **Sin texto antes, dentro ni después.**

**Convenciones de tipado (nuevas en v2, respétalas):**
- Usa **`null`** para lo desconocido o no reportado. **Nunca inventes un valor ni escribas un string vacío.**
- Los campos con **enum** admiten solo los valores listados.
- Las listas son **arrays JSON**, no objetos numerados.
- Las latencias van como **número en milisegundos** más un campo de condiciones; nunca como texto libre.
- Los `id` son estables y referenciables desde otros bloques (p. ej. `"P03.p02"`, `"PR07"`).

```json
{
  "metadata_ejecucion": {
    "version_esquema": "2.0",
    "sistema_analizado": "ViruSynth",
    "fecha_de_ejecucion": "AAAA-MM-DD",
    "ventana_temporal": "2020-2026",
    "bases_academicas_consultadas": [],
    "fuentes_de_producto_consultadas": [],
    "total_papers": 0,
    "total_productos": 0,
    "afirmaciones_con_veredicto_negativo": 0,
    "limitaciones_de_la_busqueda": ""
  },

  "P01": {
    "id": "P01",
    "titulo": "",
    "linea": "A",
    "nombre_de_linea": "Arquitectura y tiempo real",
    "resumen": "",
    "correspondencia_con_virusynth": {
      "modulos": ["bridge/main.py"],
      "afirmaciones": ["C1"],
      "veredicto": "confirma | matiza | refuta | sin_evidencia",
      "justificacion_del_veredicto": ""
    },
    "motivacion_o_caso_de_uso": "",
    "arquitectura_tecnica_dominante": "",
    "metricas_clave": [],
    "latencia_reportada": { "min_ms": null, "max_ms": null, "condiciones": null },
    "modalidad_de_interaccion": "",
    "supuestos_de_sensado_comunicacion_o_procesamiento": "",
    "validacion_y_herramientas": "",
    "ventajas": [],
    "desventajas": [],
    "trl_estimado": null,
    "costo_computacional_y_de_hardware": "",
    "alternativa_no_tomada_por_virusynth": "",
    "desafios_abiertos": [],
    "conexion_dr_oliver": null,
    "validacion_empirica_sugerida": {
      "que_medir": "",
      "como_medirlo": "",
      "esfuerzo_estimado": "bajo | medio | alto"
    },
    "nivel_de_evidencia": "alta | media | baja",
    "papers": [
      {
        "id": "P01.p01",
        "titulo": "",
        "autores": "",
        "anio": null,
        "resumen": "",
        "venue": "",
        "tipo_de_venue": "revista | conferencia | preprint | tesis | reporte_tecnico",
        "base_de_datos": "",
        "cuartil_o_ranking": null,
        "sub_tema": "",
        "arquitectura_o_tecnica_reportada": "",
        "metricas_reportadas": "",
        "relacion_con_el_problema": "",
        "afirmacion_que_toca": ["C1"],
        "postura": "apoya | contradice | neutral",
        "keywords": [],
        "citas": null,
        "github_stars": null,
        "link": "",
        "cita_ieee": ""
      }
    ]
  },

  "P02": { "…": "misma estructura que P01 · linea A · C6 · MCU → host de síntesis" },
  "P03": { "…": "misma estructura · linea A · C2 · LLM como controlador de parámetros" },
  "P04": { "…": "misma estructura · linea A · C3 · resiliencia y degradación elegante" },
  "P05": { "…": "misma estructura · linea B · C4 · audiencia participativa" },
  "P06": { "…": "misma estructura · linea B · C1, C4 · NMP y sincronización de estado" },
  "P07": { "…": "misma estructura · linea B · C5 · IA mediadora de conflictos" },
  "P08": { "…": "misma estructura · linea B · C4, C5 · evaluación de co-creatividad" },
  "P09": { "…": "misma estructura · linea C · productos y apps musicales lanzados" },
  "P10": { "…": "misma estructura · linea C · infraestructura realtime y modelo de negocio" },

  "Analisis_de_Posicionamiento": {
    "descripcion": "Contraste directo entre cada decisión arquitectónica de ViruSynth y el estado del arte encontrado.",
    "decisiones": [
      {
        "decision": "",
        "afirmacion_relacionada": "C1",
        "alternativas_documentadas": [],
        "evidencia_a_favor": [],
        "evidencia_en_contra": [],
        "veredicto": "solida | defendible_con_matices | debil | insostenible",
        "que_cambiaria_el_veredicto": ""
      }
    ]
  },

  "Matriz_de_Novedad": {
    "descripcion": "Qué es genuinamente nuevo en ViruSynth y qué no, frente a literatura, open source y productos comerciales.",
    "afirmaciones": [
      {
        "id": "C1",
        "enunciado": "",
        "nivel_de_novedad": "nulo | incremental | notable | alto",
        "trabajo_previo_mas_cercano": {
          "referencia": "",
          "tipo": "paper | repositorio | producto",
          "id_relacionado": "P01.p02 | PR03",
          "en_que_se_solapa": "",
          "en_que_difiere": ""
        },
        "argumento_de_originalidad_defendible": "",
        "riesgo_de_ser_rebatido_en_revision": "alto | medio | bajo"
      }
    ],
    "combinacion_global": {
      "es_novedosa_la_combinacion": null,
      "justificacion": "",
      "contribucion_declarable_en_un_paper": ""
    }
  },

  "Panorama_Academico_y_Open_Source": {
    "descripcion": "Sistemas, instrumentos y repositorios documentados que compiten funcionalmente con ViruSynth.",
    "soluciones": [
      {
        "id": "SOL01",
        "nombre": "",
        "autor_o_equipo": "",
        "anio": null,
        "tipo": "sistema_academico | repositorio | instrumento | dataset | framework",
        "resumen": "",
        "linea_relacionada": "A | B | C",
        "afirmaciones_que_toca": [],
        "estado_del_proyecto": "activo | inactivo | desconocido",
        "relevancia_para_originalidad": "",
        "link": ""
      }
    ]
  },

  "Panorama_Comercial_Apps_y_Plataformas": {
    "descripcion": "Productos, apps y tecnologías efectivamente lanzados (web, móvil, escritorio, plugin, hardware, SDK) que ocupan total o parcialmente el espacio de ViruSynth. Incluye productos discontinuados como evidencia de mercado.",
    "productos": [
      {
        "id": "PR01",
        "nombre": "",
        "empresa_u_organizacion": "",
        "tipo": "app_web | app_movil | app_escritorio | plugin_daw | external_pd_max | hardware | sdk_infraestructura | servicio_saas | extension_streaming | open_source",
        "plataformas": [],
        "anio_de_lanzamiento": null,
        "estado": "activo | beta | discontinuado | adquirido | desconocido",
        "ultima_actividad_verificada": null,
        "causa_de_discontinuacion": null,
        "descripcion": "",
        "categoria_funcional": "colaboracion_musical | ia_generativa_musical | sintesis_neural | instrumento_sensor | participacion_de_audiencia | infraestructura_realtime | live_coding",
        "usa_ia": null,
        "rol_de_la_ia": "genera_audio | genera_simbolico | asiste_parametros | dirige_o_media | ninguno | desconocido",
        "soporta_multiusuario_en_vivo": null,
        "latencia_declarada": { "valor_ms": null, "condiciones": null, "fuente": null },
        "modelo_de_negocio": "",
        "precio_publico": null,
        "traccion_declarada": null,
        "financiacion_o_respaldo": null,
        "abierto_o_cerrado": "abierto | cerrado | mixto | desconocido",
        "solapamiento_con_virusynth": "",
        "diferencias_clave": "",
        "amenaza_para_la_originalidad": "alta | media | baja",
        "leccion_para_virusynth": "",
        "link": "",
        "fuente_de_verificacion": ""
      }
    ],
    "sintesis_de_mercado": {
      "existe_producto_con_ia_directora_multiusuario": null,
      "hueco_de_mercado_identificado": "",
      "productos_discontinuados_y_su_leccion": "",
      "barreras_de_entrada_observadas": "",
      "viabilidad_del_modelo_saas_propuesto": ""
    }
  },

  "Ruta_de_Publicacion": {
    "descripcion": "Camino desde el prototipo verificado hasta una contribución publicable.",
    "venues_candidatos": [
      {
        "nombre": "",
        "tipo": "conferencia | revista",
        "ranking": null,
        "ajuste_con_la_contribucion": "alto | medio | bajo",
        "tipo_de_contribucion_esperado": "",
        "evidencia_minima_exigida": "",
        "fecha_limite_tipica": null,
        "riesgo_principal_de_rechazo": ""
      }
    ],
    "contribucion_principal_recomendada": "",
    "estudio_empirico_minimo_viable": {
      "diseno": "",
      "participantes": "",
      "instrumentos_de_medida": [],
      "variables_dependientes": [],
      "duracion_estimada": ""
    },
    "trabajo_faltante_ordenado_por_prioridad": []
  },

  "Recomendaciones_Accionables": {
    "mantener_sin_cambios": [],
    "modificar_con_justificacion": [
      { "que": "", "por_que": "", "evidencia": "", "esfuerzo": "bajo | medio | alto" }
    ],
    "descartar_o_reemplazar": [],
    "medir_antes_de_decidir": [],
    "riesgos_abiertos": [],
    "siguiente_paso_experimental": ""
  },

  "Vacios_de_Evidencia": {
    "descripcion": "Preguntas que la búsqueda no pudo responder. Declararlas es obligatorio; rellenarlas con suposiciones, no.",
    "vacios": [
      {
        "pregunta": "",
        "linea": "A | B | C",
        "por_que_no_se_resolvio": "no_existe_literatura | acceso_restringido | terminologia_dispersa | producto_sin_informacion_publica",
        "implicacion_para_virusynth": "",
        "como_podria_resolverse": ""
      }
    ]
  },

  "Fuentes_Fundacionales": {
    "descripcion": "6-8 trabajos clásicos (anteriores a 2020) que sustentan los principios de fondo: HCI y physical computing (p. ej. Ishii & Ullmer, 'Tangible Bits'), NIME y control gestual (Wanderley, primeros NIME), sistemas interactivos musicales (Rowe, Winkler), y arquitecturas realtime. No cuentan para el mínimo por ítem.",
    "papers": [
      { "id": "F01", "…": "mismos campos que un paper normal, incluida cita_ieee" }
    ]
  }
}
```

---

## Validaciones obligatorias antes de responder

1. **Conteo**: exactamente 10 ítems (P01–P10): 4 en línea A, 4 en línea B, 2 en línea C.
2. **Papers**: mínimo **3 por ítem** (≥30 en total) + 6–8 en `Fuentes_Fundacionales`, con indexación verificada o preprint señalado.
3. **Productos**: mínimo **12** en `Panorama_Comercial_Apps_y_Plataformas`, cubriendo al menos 5 de las categorías funcionales del enum, **incluyendo al menos 2 discontinuados o adquiridos** y al menos 2 de infraestructura realtime.
4. **Cobertura de afirmaciones**: las 6 afirmaciones C1–C6 aparecen en `Matriz_de_Novedad` y reciben veredicto en al menos un ítem.
5. **Antisesgo**: al menos una afirmación con veredicto `matiza` o `refuta`, o justificación explícita de por qué ninguna se matiza.
6. **Originalidad**: `Panorama_Academico_y_Open_Source` con ≥6 soluciones; cada `amenaza_para_la_originalidad: "alta"` debe estar justificada con el solapamiento concreto.
7. **Ruta de publicación**: ≥3 venues candidatos con evidencia mínima exigida por cada uno.
8. **Verificación de estado**: ningún producto sin `estado` ni sin `fuente_de_verificacion`.
9. **No duplicidad** entre papers, entre ítems de la misma línea, ni entre productos.
10. **Tipado**: `null` para lo desconocido (nunca strings vacíos ni valores inventados); enums respetados; latencias como número.
11. **Vacíos declarados**: `Vacios_de_Evidencia` no puede quedar vacío — si la búsqueda fue perfecta, justifícalo.
12. **Salida**: solo el JSON válido, sin texto adicional.

---

## Consultas avanzadas (Scopus e IEEE Xplore)

Sintaxis verificada: en **Scopus** usar `TITLE-ABS-KEY(...)`, booleanos en mayúsculas, `PUBYEAR > 2019 AND PUBYEAR < 2027`, comillas para frase laxa, llaves `{ }` para frase exacta, comodín `*`, y **paréntesis explícitos siempre** (Scopus está actualizando su precedencia de operadores entre finales de 2025 y comienzos de 2026). En **IEEE Xplore** (Command Search): campo entre comillas + dos puntos (`"All Metadata":`), booleanos en mayúsculas, `NEAR/n`, comodín `*`, y **espacio entre el tag de campo y el paréntesis** (bug conocido si van pegados).

**P01 — Desacoplamiento IA/audio y presupuestos de latencia asimétricos**
- Scopus: `TITLE-ABS-KEY(("interactive music system*" OR "musical agent*" OR "live performance system*") AND ("latency" OR "real-time constraint*" OR "temporal accuracy") AND ("architecture" OR "decoupl*" OR "asynchronous" OR "control rate")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE: `("All Metadata":"interactive music system" OR "All Metadata":"musical agent") AND ("All Metadata":"latency" OR "All Metadata":"real-time") AND ("All Metadata":"architecture" OR "All Metadata":"asynchronous")`

**P02 — Microcontrolador → host de síntesis (protocolo, jitter, fiabilidad)**
- Scopus: `TITLE-ABS-KEY(("ESP32" OR "Arduino" OR "microcontroller*") AND ("digital musical instrument*" OR "gestural controller*" OR "sensor interface") AND ("latency" OR "jitter" OR "serial" OR "open sound control" OR "OSC" OR "MIDI")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE: `("All Metadata":"ESP32" OR "All Metadata":"Arduino") AND ("All Metadata":"digital musical instrument" OR "All Metadata":"gestural controller") AND ("All Metadata":"latency" OR "All Metadata":"Open Sound Control")`

**P03 — LLM/agente como controlador de parámetros musicales**
- Scopus: `TITLE-ABS-KEY(("large language model*" OR "LLM" OR "foundation model*" OR "agentic") AND ("tool use" OR "function calling" OR "structured output*" OR "parameter control" OR "symbolic control") AND ("music*" OR "audio" OR "sound synthesis")) AND PUBYEAR > 2021 AND PUBYEAR < 2027`
- IEEE: `"All Metadata":"large language model" AND ("All Metadata":"music" OR "All Metadata":"sound synthesis") AND ("All Metadata":"control" OR "All Metadata":"function calling")`

**P04 — Resiliencia y degradación elegante en performance en vivo**
- Scopus: `TITLE-ABS-KEY(("fault toleran*" OR "graceful degradation" OR "fallback" OR "robustness" OR "failure mode*") AND ("live performance" OR "interactive installation*" OR "real-time system*") AND ("music*" OR "media art" OR "stage" OR "audio")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE: `("All Metadata":"graceful degradation" OR "All Metadata":"fault tolerance") AND ("All Metadata":"real-time" OR "All Metadata":"live performance") AND ("All Metadata":"audio" OR "All Metadata":"interactive system")`
- *Si el cruce resulta escaso — es probable —, amplía a fiabilidad de sistemas interactivos en HCI y declara el vacío en `Vacios_de_Evidencia`.*

**P05 — Audiencia participativa / crowd-in-the-loop**
- Scopus: `TITLE-ABS-KEY(("audience participation" OR "audience interaction" OR "crowd-sourced" OR "collective control") AND ("live music" OR "concert" OR "musical performance") AND ("mobile" OR "smartphone" OR "web" OR "real-time")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE: `("All Metadata":"audience participation" OR "All Metadata":"audience interaction") AND ("All Metadata":"live music" OR "All Metadata":"musical performance") AND ("All Metadata":"mobile" OR "All Metadata":"real-time")`

**P06 — Networked Music Performance y sincronización de estado**
- Scopus: `TITLE-ABS-KEY(("networked music performance" OR "telematic music" OR "distributed musical interaction") AND ("latency" OR "synchroni*" OR "jitter" OR "state synchroni*" OR "clock")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE: `("All Metadata":"networked music performance" OR "All Metadata":"telematic performance") AND ("All Metadata":"latency" OR "All Metadata":"synchronization")`

**P07 — IA mediadora de conflictos creativos / iniciativa mixta**
- Scopus: `TITLE-ABS-KEY(("mixed-initiative" OR "shared agency" OR "mediat*" OR "conflict resolution" OR "arbitrat*") AND ("co-creativ*" OR "human-AI collaboration" OR "creativity support tool*") AND ("music*" OR "creative work")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE: `("All Metadata":"mixed-initiative" OR "All Metadata":"human-AI collaboration") AND ("All Metadata":"co-creativity" OR "All Metadata":"creativity support") AND "All Metadata":"music"`

**P08 — Evaluación de co-creatividad y agencia compartida**
- Scopus: `TITLE-ABS-KEY(("user stud*" OR "evaluation" OR "questionnaire" OR "creativity support index" OR "sense of agency") AND ("co-creativ*" OR "human-AI collaboration" OR "interactive music system*") AND ("musician*" OR "music*" OR "performer*")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE: `("All Metadata":"creativity support index" OR "All Metadata":"sense of agency" OR "All Metadata":"user study") AND ("All Metadata":"music" OR "All Metadata":"co-creative")`

**P09 — Productos y apps de creación musical colaborativa/asistida**
- Scopus (contexto de adopción y mercado, complementario a la búsqueda de campo): `TITLE-ABS-KEY(("music technology" OR "music production software" OR "collaborative music platform*") AND ("adoption" OR "user stud*" OR "commercial" OR "market" OR "prosumer")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- **Búsqueda primaria no académica**: Product Hunt + App Store/Play (categoría Música, ordenar por lanzamientos recientes) + GitHub topics + prensa especializada. Registrar fecha de última actualización como prueba de vida.

**P10 — Infraestructura realtime y sincronización multiusuario**
- Scopus: `TITLE-ABS-KEY(("real-time collaboration" OR "multi-user synchroni*" OR "conflict-free replicated data type*" OR "CRDT" OR "operational transformation") AND ("web" OR "cloud" OR "platform" OR "WebSocket*") AND ("latency" OR "scalab*" OR "consistency")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- **Búsqueda primaria no académica**: documentación y pricing de Portal, Ably, PubNub, Liveblocks, PartyKit, Cloudflare Durable Objects/Calls; extraer límites de latencia y coste por conexión concurrente.

**Otras bases** (ACM DL, SpringerLink, ScienceDirect, Google Scholar): adaptar las mismas combinaciones al buscador avanzado de cada plataforma. Google Scholar no soporta proximidad — usar frases exactas entre comillas y revisar manualmente los primeros 3–4 resultados por consulta.

---

## Importante

- **Rigor cuantitativo primero.** Para la Línea A: presupuestos de latencia por etapa (sensor → MCU → transporte → host → DSP), jitter, throughput y overhead de protocolo — el investigador viene de telecomunicaciones y detectará cualquier vaguedad en esto. Para la Línea B: umbrales temporales de sincronía percibida, tamaños muestrales y escalas validadas. Para la Línea C: cifras, precios y fechas verificables, no adjetivos de marketing.
- **Contrasta siempre contra los números reales de ViruSynth** de la tabla de métricas, no contra valores genéricos.
- **Declara los vacíos.** Si algo no se encuentra, va a `Vacios_de_Evidencia`. Rellenarlo con suposiciones plausibles es el peor resultado posible de este estudio.
- **Un producto discontinuado es un hallazgo, no un descarte.** Regístralo con su causa.
- Cita en formato **IEEE completo** (autores, título, venue, año, DOI) en `cita_ieee`.
- Si al terminar la conclusión es *"ViruSynth no aporta nada nuevo"*, esa es una salida legítima y valiosa: dilo en `Matriz_de_Novedad.combinacion_global` con la evidencia que lo sustenta.
