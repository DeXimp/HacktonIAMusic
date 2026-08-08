# Prompt para Deep Research — Estado del Arte: IA en Tiempo Real — Interacción con el Mundo Físico vs. Colaborador Musical
### (Adaptado del prompt original AIMA — Estado del Arte para CONCYTEC-PROCIENCIA E041-2026-05, "Detección de Armas")

---

## Rol / Objetivo

Actúa como un **investigador senior en sistemas ciberfísicos, Computer Music/NIME, Human-Computer Interaction (HCI) e Inteligencia Artificial aplicada**, con capacidad de verificar indexación de literatura científica (Scopus/IEEE Xplore/ACM Digital Library) y de mapear el panorama de herramientas, instrumentos y proyectos ya existentes (GitHub, NIME Archive, Hackster.io, Devpost). Tu tarea es generar **10 ítems técnicos** (P01–P10), agrupados en **2 líneas de investigación**, que en conjunto constituyan un Estado del Arte riguroso y comparativo para decidir qué línea desarrollar en un **hackathon de IA en tiempo real**, tras un taller de Arduino + Pure Data, con miras a una eventual **publicación científica**.

No asumas de antemano cuál línea es superior: ambas deben desarrollarse con el mismo rigor, y la recomendación final debe poder resolverse en cualquier dirección.

**La salida final debe ser el objeto JSON especificado en la sección "Formato de salida (obligatorio)". No adelantes conclusiones fuera de ese JSON.**

---

## Contexto del proyecto

- **Investigador**: ingeniero electricista-electrónico (UNI-FIEE), con experiencia en telecomunicaciones, RF, microondas y redes de formación de haz (matriz de Butler); **sin experiencia previa específica en Human-Computer Interaction, Physical Computing musical, NIME, ni en el desarrollo de agentes de IA en tiempo real**. Esta asimetría es relevante para la sección "Calidad y cobertura": el investigador está técnicamente más cerca de la Línea 1 (sensores, protocolos de comunicación) por su formación, y del instructor del taller para la Línea 2 por autoridad/mentoría — dos sesgos distintos a vigilar.
- **Convocatoria**: taller **"Microcontroladores, música y arte sonoro: integración entre Arduino y Pure Data"**, dictado por el **Dr. Jaime Oliver La Rosa** (Associate Professor of Music/Composition y Director of Graduate Studies, New York University; co-director de los NYU Waverly Labs for Computing and Music; PhD en Computer Music por UC San Diego bajo la dirección de Miller Puckette, creador de Pure Data), en el marco de un hackathon de IA en tiempo real.
- **Línea de investigación del Dr. Oliver relevante para la Línea 2**: diseño de instrumentos musicales electrónicos que "escuchan, entienden, recuerdan y responden"; controladores de código abierto **Silent Drum** y **MANO**, que usan técnicas de visión por computador para rastrear y clasificar gestos de la mano en tiempo real; trabajo extensivo con Pure Data y notación asistida por computadora.
  > ⚠️ **Completar y verificar antes de usar este documento**: nombre/fecha/duración exactas del hackathon, organizador, criterios de evaluación del jurado, y hardware/API de LLM efectivamente disponibles. Ajustar la siguiente tabla y la sección "Condiciones de factibilidad" con estos datos reales.

| Parámetro | Valor de referencia (ajustar con datos reales) |
|---|---|
| Duración típica de un hackathon de IA en tiempo real | 24–48 horas continuas |
| Tamaño de equipo típico | 2–5 personas |
| Hardware asumido disponible | 1–2 Arduino/ESP32 + sensores básicos (IMU, FSR, ultrasónico, flex, micrófono) |
| Acceso a modelos de IA asumido | APIs comerciales de LLM con function calling/tool use, y/o modelos locales ligeros |
| Criterios de evaluación típicos | Innovación técnica, viabilidad de demo en vivo, claridad de la propuesta, impacto/originalidad |

---

## Estructura de los 10 ítems (P01–P10)

Los 10 ítems se agrupan en **2 Líneas de Investigación**. Cada ítem debe ser una variante técnica genuinamente distinta dentro de su línea (no una reformulación superficial de otro ítem de la misma línea):

**Línea 1 — "AI Interacting with the Physical World" (P01–P05)**
- P01 — Arquitecturas AIoT/ciberfísicas: adquisición de sensores (Arduino/ESP32) y transmisión de datos en tiempo real
- P02 — Plataformas colaborativas multiusuario para monitoreo compartido de sistemas físicos en tiempo real (tipo dashboard)
- P03 — LLMs y agentes para interpretación de eventos, detección de anomalías y respuesta a consultas sobre datos de sensores
- P04 — Digital twins y fusión de sensores para representar el estado de un sistema físico
- P05 — Edge AI / Embodied AI: inferencia en el borde sobre microcontroladores para reducir latencia y dependencia de conectividad

**Línea 2 — "AI Music Collaborator" (P06–P10)**
- P06 — NIME (New Interfaces for Musical Expression) e instrumentos musicales digitales basados en sensores + Arduino
- P07 — Interacción gestual y control sensorial de procesos sonoros mediante Pure Data/Max
- P08 — LLMs y agentes de IA para improvisación, co-creación musical y generación algorítmica en tiempo real
- P09 — Sonificación: mapeo de datos/gestos a parámetros sonoros de forma perceptualmente coherente
- P10 — Colaboración humano-IA en instrumentos musicales digitales: co-creatividad, agencia compartida y estudios de usuario

Si durante la investigación se descubre que alguno de estos 10 ítems no tiene sustento suficiente en literatura o es técnicamente inviable, reemplázalo por una variante equivalente dentro de la misma línea, dejando constancia del reemplazo en el campo "Desafíos Abiertos Relacionados".

---

## Preguntas de investigación por línea

### Línea 1 — AI Interacting with the Physical World (P01–P05)
- Arquitecturas de referencia end-to-end: sensor → microcontrolador (Arduino/ESP32) → protocolo de comunicación (Serial/WiFi/BLE/MQTT/WebSockets/OSC) → backend/plataforma colaborativa → LLM (vía function calling, tool use o RAG) → interfaz multiusuario. ¿Qué latencias por etapa (ms) reportan los estudios recientes?
- Estrategias de sensor fusion y digital twins ligeros, ejecutables con los recursos típicos de un hackathon (sin infraestructura industrial).
- Arquitecturas agénticas de LLM sobre streams de datos de sensores para detección de anomalías e interpretación de eventos: taxonomías recientes distinguen agentes "solo detección" (bajo costo, baja interpretabilidad) de agentes "de razonamiento" (más costosos, más interpretables) — ¿qué trade-off reportan los estudios 2024–2026?
- Métricas de evaluación reportadas para colaboración humano-IA en sistemas de monitoreo: tiempo de detección de anomalías, tasa de falsos positivos/negativos, confianza/satisfacción del usuario, viabilidad de modelos locales (edge) frente a APIs en la nube.
- Consumo energético y viabilidad de inferencia en el borde (TinyML) vs. inferencia en la nube para escenarios de tiempo real con microcontroladores tipo ESP32.

### Línea 2 — AI Music Collaborator (P06–P10)
- Presupuesto de latencia end-to-end aceptable en interacción musical en tiempo real (típicamente <10–20 ms para una sensación de "tocar en vivo"): ¿qué arquitecturas Arduino + Pure Data/Max + IA reportan cumplir este umbral, y cuáles operan en régimen no estrictamente tiempo real (generación por bloques, latencia de segundos)?
- Protocolos de comunicación entre Arduino y Pure Data/Max (Serial/Firmata, OSC sobre WiFi, MIDI) y su impacto en jitter/latencia reportado en literatura NIME.
- Modelos generativos musicales evaluados en tareas de improvisación/co-creación en vivo: desde sistemas simbólicos multiagente hasta modelos de difusión latente o agentes de lenguaje musical — ¿qué arquitecturas están documentadas operando en vivo con músicos reales (no solo offline)?
- Métricas de evaluación de co-creatividad reportadas (percepción de agencia compartida, estudios con músicos profesionales, protocolos Wizard-of-Oz, cuestionarios de creatividad percibida).
- Estrategias de mapeo (parameter mapping / sonification) reportadas para vincular gestos y datos de sensores a parámetros sonoros de forma perceptualmente coherente.

### Transversal (todos los ítems)
- Proyectos, instrumentos o repositorios de código abierto ya documentados (NIME Archive, GitHub, Hackster.io, Devpost) que compitan directamente en funcionalidad con el ítem, para el análisis de originalidad.
- Conexión explícita con la línea de investigación del Dr. Jaime Oliver La Rosa (Silent Drum, MANO, Pure Data) cuando aplique.
- Con qué posible categoría/track del hackathon encaja mejor cada ítem (si se conocen las categorías, completar; si no, dejar el campo como "no reportado / a definir con las bases del hackathon").

---

## Condiciones de factibilidad (obligatorias)

- Cada ítem debe evaluarse bajo las restricciones reales del hackathon: duración, hardware disponible, acceso a APIs de LLM, tamaño de equipo (ajustar según la tabla de la sección "Contexto del proyecto").
- Priorizar arquitecturas prototipables con hardware accesible (Arduino Uno/Nano, ESP32, sensores comunes) y modelos de IA de acceso público vía API o modelos locales ligeros.
- Señalar explícitamente cuándo un ítem requeriría entrenamiento o fine-tuning de modelos propios (alto costo de tiempo, generalmente inviable en el marco de un hackathon) frente a uso de modelos pre-entrenados vía prompting/API/agentes.

## Requisitos de las fuentes

- Bases de datos priorizadas, en este orden: **Scopus, IEEE Xplore, ACM Digital Library, SpringerLink, ScienceDirect, Google Scholar**.
- Priorizar publicaciones indexadas en cuartiles **Q1/Q2** (SJR o JCR) cuando la fuente sea una revista. Para venues de conferencia sin cuartil de revista (**NIME, CHI, ISMIR, ICMC, UIST, TEI, ACM Multimedia, DIS**), usar como criterio de calidad equivalente el ranking **CORE (A\*/A cuando esté disponible)** o el hecho de ser el venue de referencia reconocido del subcampo; registrar el ranking (o su ausencia) como dato informativo, sin excluir por este criterio.
- Ventana temporal: **2020–2026**. Excepciones fundacionales anteriores a 2020 van en `Fuentes_Fundacionales`, no en los papers de cada ítem.
- Preprints (arXiv) se admiten si están claramente señalados como tales y aportan evidencia reciente relevante (frecuente en LLMs/IA generativa dado el ritmo de publicación del campo).
- Idioma: literatura técnica principalmente en inglés; se admite español para contexto institucional peruano (INICTEL-UNI, UNI, eventos/talleres locales).
- Cada paper debe respaldar explícitamente al menos uno de: (a) motivación/caso de uso, (b) marco teórico/arquitectura de referencia, (c) viabilidad técnica/experimental o evaluación de usuario.

## Calidad y cobertura

- Los 5 ítems de cada línea deben ser técnicamente distintos entre sí (no reformulaciones superficiales del mismo enfoque).
- Sin duplicidad: cada paper se usa una sola vez con un rol claro; no reciclar el mismo paper entre ítems salvo revisiones/surveys que abarquen varios ítems, señalándolo explícitamente en `relación con el problema`.
- Ambas líneas deben desarrollarse con la misma profundidad y rigor. Vigilar dos sesgos posibles, en direcciones opuestas: **(a)** sesgo hacia la Línea 1 por cercanía al perfil de telecomunicaciones/RF del investigador (sensores, protocolos de comunicación), y **(b)** sesgo hacia la Línea 2 por ser la línea de investigación explícita del instructor del taller. Ninguna cercanía previa debe determinar la `Recomendacion_Preliminar`; esta debe basarse exclusivamente en la evidencia recopilada.

---

## Formato de salida (obligatorio)

Devuelve **exclusivamente** un único objeto JSON con las claves `P01` a `P10`, más los bloques `Analisis_Comparativo`, `Panorama_Soluciones_Existentes`, `Recomendacion_Preliminar` y `Fuentes_Fundacionales`. **No incluyas texto adicional, explicaciones ni comentarios fuera del JSON.**

> Nota sobre los 3 bloques adicionales a `Fuentes_Fundacionales`: el análisis comparativo entre líneas y el panorama de soluciones existentes son transversales a los 10 ítems y no caben dentro de uno solo — por eso van como bloques propios en vez de repetirse en cada P0X. `Panorama_Soluciones_Existentes` cumple, en este contexto de hackathon, el mismo rol que un análisis de novedad frente a patentes cumpliría en una convocatoria formal: establecer qué tan original es cada ítem frente al estado actual de la práctica.

```json
{
  "P01": {
    "Título": "",
    "Línea de Investigación": "",
    "Resumen": "",
    "Motivación / Caso de Uso": "",
    "Arquitectura Técnica Dominante": "",
    "Métricas Clave": "",
    "Modalidad de Interacción / Escenario de Uso": "",
    "Supuestos de Sensado, Comunicación o Procesamiento": "",
    "Validación y Herramientas": "",
    "Ventajas": "",
    "Desventajas": "",
    "Madurez / Nivel de Prototipo (TRL estimado)": "",
    "Costo Computacional / de Hardware y Viabilidad para el Hackathon": "",
    "Desafíos Abiertos Relacionados": "",
    "Conexión con la Línea del Dr. Jaime Oliver La Rosa (si aplica)": "",
    "papers": {
      "p01": {
        "título": "",
        "autores": "",
        "resumen": "",
        "venue": "",
        "base de datos / editorial": "",
        "cuartil o ranking (CORE / impacto)": "",
        "año": "",
        "sub_tema": "",
        "arquitectura o técnica reportada": "",
        "métricas reportadas": "",
        "relación con el problema": "",
        "key words": "",
        "popularidad (citas / GitHub stars)": "",
        "link": "",
        "cita IEEE": ""
      },
      "p02": { "...": "mismos campos que p01" },
      "p0N": { "...": "continuar hasta cubrir la cantidad necesaria (mínimo 3 por ítem)" }
    }
  },
  "P02": { "...": "mismos campos que P01, línea: L1 — Plataformas colaborativas multiusuario" },
  "P03": { "...": "..." },
  "P04": { "...": "..." },
  "P05": { "...": "mismos campos que P01, línea: L1 — Edge AI / Embodied AI" },
  "P06": { "...": "mismos campos que P01, línea: L2 — NIME e instrumentos musicales digitales" },
  "P07": { "...": "..." },
  "P08": { "...": "..." },
  "P09": { "...": "..." },
  "P10": { "...": "mismos campos que P01, línea: L2 — Colaboración humano-IA y co-creatividad" },
  "Analisis_Comparativo": {
    "descripción": "Comparación cruzada de las 2 líneas de investigación en los criterios de decisión relevantes para el hackathon y la eventual publicación.",
    "tabla": [
      {
        "linea": "",
        "complejidad_dado_perfil_del_investigador": "",
        "viabilidad_en_marco_temporal_del_hackathon": "",
        "disponibilidad_y_madurez_de_herramientas_sdks_apis": "",
        "requisitos_de_latencia_tiempo_real": "",
        "disponibilidad_y_calidad_de_datos_o_ejemplos": "",
        "grado_de_novedad": "",
        "alineacion_con_mentoria_disponible": "",
        "potencial_de_impacto_ante_jurado": "",
        "potencial_de_publicacion_futura": "",
        "riesgos_principales": ""
      }
    ]
  },
  "Panorama_Soluciones_Existentes": {
    "descripción": "Proyectos, instrumentos, repositorios y soluciones ya documentadas, relevantes para el análisis de originalidad frente al estado actual de la práctica (equivalente funcional al análisis de novedad frente a patentes en una convocatoria formal).",
    "soluciones": {
      "sol01": {
        "nombre": "",
        "autor_o_equipo": "",
        "año": "",
        "resumen": "",
        "linea_relacionada": "",
        "tipo": "",
        "relevancia_para_originalidad": "",
        "link": ""
      },
      "sol0N": { "...": "continuar hasta cubrir mínimo 6, cubriendo ambas líneas" }
    }
  },
  "Recomendacion_Preliminar": {
    "linea_o_item_recomendado": "",
    "justificación": "",
    "riesgos_abiertos": "",
    "siguiente_paso_experimental_sugerido": "",
    "camino_hacia_publicacion_cientifica": ""
  },
  "Fuentes_Fundacionales": {
    "descripción": "Máximo 6-8 papers/libros clásicos (anteriores a 2020) que sustentan los principios fundamentales de HCI/Physical Computing (p. ej. Ishii & Ullmer, 'Tangible Bits'), de NIME/control gestual (p. ej. primeros papers de la conferencia NIME, trabajos de Wanderley sobre control gestual musical), o de sistemas ciberfísicos/IoT tempranos. No cuentan para el mínimo de papers recientes exigido por ítem.",
    "papers": {
      "f01": { "...": "mismos campos que un paper normal, incluida cita IEEE" },
      "f0N": { "...": "continuar hasta cubrir 6-8" }
    }
  }
}
```

## Validaciones obligatorias antes de responder

1. **Conteo**: exactamente 10 ítems (P01–P10), 5 por cada una de las 2 líneas.
2. **Papers**: mínimo 3 por ítem (mínimo 30 en total) + 6-8 en `Fuentes_Fundacionales`; indexación verificada (Scopus/IEEE Xplore/ACM DL/SpringerLink/ScienceDirect) o preprint claramente señalado como tal.
3. **Relevancia**: cada ítem completa `Línea de Investigación` y, cuando aplique, `Conexión con la Línea del Dr. Jaime Oliver La Rosa`.
4. **Factibilidad real**: contrastada contra las restricciones de hackathon indicadas en "Contexto del proyecto" (duración, hardware, acceso a IA, equipo).
5. **Originalidad**: `Panorama_Soluciones_Existentes` incluye mínimo 6 soluciones/proyectos, cubriendo ambas líneas.
6. **No duplicidad** entre papers ni entre ítems de la misma línea.
7. **Balance**: ambas líneas desarrolladas con la misma profundidad (verificar explícitamente ausencia de los dos sesgos descritos en "Calidad y cobertura").
8. **Campos completos**: ningún campo del JSON queda vacío; si falta evidencia para un ítem, se reemplaza por otro que sí la tenga (dejando constancia en "Desafíos Abiertos Relacionados").
9. **Salida**: responde **solo** con el JSON válido, sin texto adicional antes, dentro o después de él.

---

## Estrategia de búsqueda sugerida (interno)

- **Literatura técnica**: IEEE Xplore, ACM Digital Library (incl. actas de NIME, CHI, UIST, TEI, ISMIR, ICMC, DIS, ACM Multimedia), Scopus, SpringerLink, ScienceDirect, Google Scholar, arXiv (categorías cs.SD, cs.HC, cs.MA, cs.RO).
- **Repositorios y proyectos**: NIME Archive (nime.org), GitHub, Hackster.io, Devpost (proyectos de hackathons previos), Google Magenta.
- **Documentación de hardware**: Arduino, Espressif (ESP32), datasheets de sensores comunes (IMU, FSR, ultrasónico, flex sensors, micrófonos MEMS).
- **Panorama de soluciones existentes**: GitHub trending, NIME Archive, Hackster.io y Devpost como equivalente funcional del análisis de patentes en este contexto (no se requiere búsqueda formal en Google Patents/WIPO salvo que algún ítem involucre un componente de hardware patentable).
- **Contexto institucional**: página del Dr. Jaime Oliver La Rosa en NYU (as.nyu.edu) y NYU Waverly Labs for Computing and Music; INICTEL-UNI si el hackathon tiene vínculo institucional; página del organizador del hackathon.

---

## Consultas avanzadas (Scopus e IEEE Xplore)

Sintaxis de referencia verificada: en **Scopus**, usar `TITLE-ABS-KEY(...)`, operadores booleanos en mayúsculas (`AND`, `OR`, `AND NOT`), `PUBYEAR > 2019 AND PUBYEAR < 2027`, comillas para frase laxa y llaves `{ }` para frase exacta, comodín `*`; **usar siempre paréntesis explícitos** para agrupar términos, dado que Scopus está actualizando su orden de precedencia de operadores booleanos entre fines de 2025 y comienzos de 2026. En **IEEE Xplore** (Command Search), anteponer el campo entre comillas seguido de dos puntos (p. ej. `"All Metadata":`), operadores en mayúsculas (`AND`, `OR`, `NOT`, `NEAR/n`, `ONEAR/n`), comodín `*`; dejar un espacio entre el tag de campo y el paréntesis de apertura (existe un bug conocido de interpretación cuando van pegados).

**P01 — Arquitecturas AIoT/ciberfísicas (sensores → tiempo real)**
- Scopus: `TITLE-ABS-KEY(("cyber-physical system*" OR "AIoT" OR "AI-enabled IoT") AND ("architecture" OR "framework") AND ("microcontroller*" OR "Arduino" OR "ESP32" OR "embedded system*")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE Xplore: `("All Metadata":"cyber-physical system" OR "All Metadata":"AIoT") AND ("All Metadata":"architecture" OR "All Metadata":"framework") AND ("All Metadata":"Arduino" OR "All Metadata":"ESP32")`

**P02 — Plataformas colaborativas multiusuario en tiempo real**
- Scopus: `TITLE-ABS-KEY(("collaborative" OR "multi-user") AND ("dashboard" OR "monitoring platform" OR "shared visualization") AND ("real-time" OR "sensor data")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE Xplore: `("All Metadata":"collaborative dashboard" OR "All Metadata":"multi-user monitoring") AND "All Metadata":"real-time"`

**P03 — LLMs/agentes para interpretación de eventos y detección de anomalías**
- Scopus: `TITLE-ABS-KEY(("large language model*" OR "LLM" OR "generative AI" OR "agentic AI") AND ("anomaly detection" OR "decision support" OR "event interpretation") AND ("sensor*" OR "IoT" OR "cyber-physical")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE Xplore: `("All Metadata":"large language model" OR "All Metadata":"agentic AI") AND ("All Metadata":"anomaly detection" OR "All Metadata":"decision support") AND "All Metadata":"sensor"`

**P04 — Digital twins y fusión de sensores**
- Scopus: `TITLE-ABS-KEY(("digital twin*") AND ("sensor fusion" OR "multi-sensor" OR "multimodal sensor*") AND ("real-time" OR "real time")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE Xplore: `"All Metadata":"digital twin" AND ("All Metadata":"sensor fusion" OR "All Metadata":"multi-sensor") AND "All Metadata":"real-time"`

**P05 — Edge AI / Embodied AI en microcontroladores**
- Scopus: `TITLE-ABS-KEY(("edge AI" OR "edge computing" OR "TinyML" OR "embodied AI" OR "embodied agent*") AND ("Arduino" OR "ESP32" OR "microcontroller*")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE Xplore: `("All Metadata":"edge AI" OR "All Metadata":"TinyML" OR "All Metadata":"embodied AI") AND ("All Metadata":"Arduino" OR "All Metadata":"ESP32" OR "All Metadata":"microcontroller")`

**P06 — NIME e instrumentos musicales digitales**
- Scopus: `TITLE-ABS-KEY(("new interface* for musical expression" OR "NIME" OR "digital musical instrument*" OR "DMI") AND ("machine learning" OR "artificial intelligence" OR "deep learning")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE Xplore: `("All Metadata":"digital musical instrument" OR "All Metadata":"new interfaces for musical expression") AND ("All Metadata":"machine learning" OR "All Metadata":"artificial intelligence")`

**P07 — Interacción gestual y control sensorial (Pure Data/Max)**
- Scopus: `TITLE-ABS-KEY(("gestural control" OR "gesture recognition") AND ("music*" OR "sonification" OR "sound synthesis") AND ("sensor*" OR "Arduino" OR "accelerometer" OR "IMU")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE Xplore: `("All Metadata":"gesture recognition" OR "All Metadata":"gestural control") AND ("All Metadata":"music" OR "All Metadata":"sonification") AND ("All Metadata":"sensor" OR "All Metadata":"Arduino")`

**P08 — LLMs/agentes para improvisación y co-creación musical**
- Scopus: `TITLE-ABS-KEY(("co-creative" OR "human-AI collaboration" OR "musical improvisation" OR "algorithmic composition") AND ("large language model*" OR "generative model*" OR "generative AI" OR "diffusion model*") AND ("music*" OR "audio")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE Xplore: `("All Metadata":"musical improvisation" OR "All Metadata":"co-creative music" OR "All Metadata":"algorithmic composition") AND ("All Metadata":"large language model" OR "All Metadata":"generative AI")`

**P09 — Sonificación y mapeo de datos a parámetros sonoros**
- Scopus: `TITLE-ABS-KEY(("sonification" OR "data-driven sound" OR "parameter mapping") AND ("real-time" OR "interactive")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE Xplore: `"All Metadata":"sonification" AND ("All Metadata":"real-time" OR "All Metadata":"interactive mapping")`

**P10 — Colaboración humano-IA y co-creatividad en instrumentos digitales**
- Scopus: `TITLE-ABS-KEY(("human-AI collaboration" OR "human-computer collaboration" OR "co-creativity") AND ("digital musical instrument*" OR "NIME" OR "interactive music system*")) AND PUBYEAR > 2019 AND PUBYEAR < 2027`
- IEEE Xplore: `("All Metadata":"human-AI collaboration" OR "All Metadata":"co-creativity") AND ("All Metadata":"digital musical instrument" OR "All Metadata":"interactive music system")`

**Otras bases (ACM DL, SpringerLink, ScienceDirect, Google Scholar)**: adaptar las mismas combinaciones de términos entre comillas con operadores `AND`/`OR` en el buscador avanzado de cada plataforma (ACM DL soporta sintaxis similar a Scopus vía su Advanced Search; SpringerLink y ScienceDirect usan formularios con campos title/abstract/keywords; Google Scholar no soporta operadores de proximidad, por lo que ahí conviene usar frases exactas entre comillas y revisar manualmente los primeros 3-4 resultados por búsqueda).

**Ejemplos recientes (2025–2026) útiles como semilla de vocabulario** — no reemplazan la búsqueda sistemática, pero ayudan a calibrar los términos: sistemas de improvisación en vivo tipo *jam_bot* (MIT Media Lab, publicado en CHI 2026/ISMIR), composición sinfónica/simbólica multiagente con LLMs (p. ej. *CoComposer*, sobre el framework AutoGen), generación de acompañamiento en tiempo real combinando modelos de difusión latente con Max/MSP, y en la Línea 1, encuestas recientes sobre detección de anomalías agéntica/multimodal con LLMs y *pipelines* de razonamiento LLM aplicados a series temporales de sensores domésticos/industriales.

---

## Importante

- Prioriza rigor técnico en ambas líneas, dado el perfil de telecomunicaciones del investigador: para la Línea 1, presupuestos de latencia por etapa (sensor → MCU → red → LLM → interfaz) y modelos de comunicación (throughput, jitter, overhead de protocolo); para la Línea 2, presupuestos de latencia de audio en tiempo real y precisión temporal de sincronización gestual-sonora. Evita explicaciones superficiales de los principios de procesamiento de señales o comunicación en tiempo real.
- Menciona explícitamente cuándo un ítem sería validable mediante prototipo software (p. ej. patch de Pure Data, simulación en Python, mock de API de LLM) antes de requerir hardware físico ensamblado.
- Prioriza métricas cuantificables y comparables entre ítems (latencia en ms, throughput, mAP/F1 cuando aplique, tasa de falsos positivos/negativos, resultados de estudios de usuario con escalas validadas).
- Usa formato de cita IEEE completo en el campo "cita IEEE" de cada paper (autores, título, venue, año, DOI).
- Señala explícitamente cualquier vacío de evidencia en vez de rellenarlo con suposiciones.
