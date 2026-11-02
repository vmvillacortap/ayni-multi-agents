# Guía de Modelos Google AI (Noviembre 2026)

Este documento clasifica y describe el amplio catálogo de modelos disponibles en tu API, detallando sus casos de uso ideales y recomendaciones arquitectónicas para integraciones en producción.

---

## 1. Modelos de Uso General (Texto y Razonamiento)
Los caballos de batalla para la mayoría de aplicaciones de chat, análisis y generación de texto.

### Familia Gemini 3.x y 4 (Vanguardia)
*   **`models/gemini-4-argon`**
    *   **Caso de uso:** El modelo más avanzado. Ideal para razonamiento matemático complejo, arquitectura de software de alto nivel y tareas deductivas profundas.
    *   **Recomendación:** Úsalo solo para problemas donde los modelos 3.x fallan. Su costo de inferencia y latencia suele ser mayor; no usar para chats triviales.
*   **`models/gemini-3.8-flash`** / **`models/gemini-3.7-flash`** / **`models/gemini-3.6-flash`** / **`models/gemini-3.5-flash`**
    *   **Caso de uso:** La familia "Flash" es el estándar de la industria para velocidad y rentabilidad.
    *   **Recomendación:** Usa siempre la versión más reciente (ej. `3.8-flash`) para el 90% de tus aplicaciones. Ofrecen la mejor relación calidad/precio para chatbots, resúmenes y extracción de datos.
*   **`models/gemini-3.1-pro-preview`**
    *   **Caso de uso:** Tareas que requieren un contexto masivo o razonamiento denso sin llegar al costo de un modelo v4.
    *   **Recomendación:** Ideal para análisis de bases de código completas o documentos legales extensos.

### Familia Lite y Nano (Baja Latencia / Edge)
*   **`models/gemini-3.5-flash-lite`** / **`models/gemini-3.1-flash-lite`** / **`models/gemini-2.5-flash-lite`**
    *   **Caso de uso:** Enrutamiento de prompts (routers), clasificación ultrarrápida de intenciones o micro-tareas automatizadas.
    *   **Recomendación:** Consúmelos cuando necesites miles de ejecuciones por minuto a un costo casi cero. Su razonamiento lógico es limitado.
*   **`models/nano-banana-pro-preview`** / **`models/gemini-nano-banana-2.1`**
    *   **Caso de uso:** Modelos optimizados para entornos con recursos limitados (Edge/Móviles) o experimentación local.
    *   **Recomendación:** Usar cuando la privacidad de datos requiera procesamiento local (si la API lo permite en modo bridge) o para latencias ultra bajas en dispositivos finales.

### Familia Gemini 2.5 (Legacy Estable)
*   **`models/gemini-2.5-pro`** / **`models/gemini-2.5-flash`**
    *   **Caso de uso:** Entornos de producción heredados que requieren máxima estabilidad y cuyos prompts fueron calibrados específicamente para esta generación.
    *   **Recomendación:** Evitar para nuevos proyectos. Migrar a 3.5+ a menos que haya una regresión de rendimiento específica.

---

## 2. Modelos Multimodales Nativos (Omni & Visión)
Especializados en procesar y entender múltiples formatos simultáneamente.

### Gemini Omni
*   **`models/gemini-omni-1.1-flash`** / **`models/gemini-omni-flash-preview`**
    *   **Caso de uso:** Interacciones de voz-a-voz, video en tiempo real o cualquier tarea donde se crucen audio, texto e imagen sin pasos intermedios.
    *   **Recomendación:** El modelo definitivo para asistentes virtuales de próxima generación. Reduce drásticamente la latencia al no requerir modelos de transcripción (ASR) o síntesis (TTS) separados.

### Especializados en Visión / Imagen
*   **`models/gemini-3-pro-image`** / **`models/gemini-3.1-flash-image`** / **`models/gemini-2.5-flash-image`**
    *   **Caso de uso:** Análisis complejo de radiografías, planos arquitectónicos, reconocimiento óptico de caracteres (OCR) avanzado o comprensión espacial densa.
    *   **Recomendación:** Usa los modelos `-image` cuando la tarea visual requiere una precisión hiper-específica que un modelo general (como `3.5-flash`) no logra captar.

---

## 3. Audio, Voz y Música
Modelos entrenados para el dominio sonoro.

*   **`models/gemini-3.8-flash-tts`** / **`models/gemini-3.1-flash-tts-preview`** / **`models/gemini-2.5-pro-preview-tts`**
    *   **Caso de uso:** Generación de respuestas habladas altamente naturales (Text-to-Speech) junto con la respuesta de texto.
    *   **Recomendación:** Consúmelos para crear bots telefónicos, lectores de audiolibros interactivos o avatares.
*   **`models/gemini-3.5-transcribe`**
    *   **Caso de uso:** Transcripción de audio masiva (Speech-to-Text), diarización (identificar quién habla) y análisis de llamadas.
    *   **Recomendación:** Ideal para procesar horas de reuniones grabadas o podcasts.
*   **Familia Lyria (`models/lyria-3.5`, `lyria-3-pro-preview`, `lyria-3-clip-preview`)**
    *   **Caso de uso:** Generación de música, efectos de sonido y edición de audio basada en IA (tecnología de Google DeepMind).
    *   **Recomendación:** Úsalo exclusivamente para proyectos creativos, generación de bandas sonoras o jingles comerciales.

---

## 4. Agentes Autónomos y Herramientas Especiales
Modelos diseñados para interactuar con el entorno o realizar tareas de larga duración.

### Deep Research (Investigación Profunda)
*   **`models/deep-research-max-preview-04-2026`** / **`models/deep-research-preview-04-2026`**
    *   **Caso de uso:** Tareas que requieren navegar por internet, leer múltiples fuentes, planificar a largo plazo y sintetizar informes de investigación exhaustivos.
    *   **Recomendación:** Consúmelo de forma asíncrona. Estos modelos "piensan" y buscan durante minutos u horas. No aptos para chats en tiempo real.

### Computer Use & Robotics
*   **`models/gemini-2.5-computer-use-preview-10-2025`**
    *   **Caso de uso:** Automatización de interfaces de usuario (RPA). El modelo puede ver la pantalla, mover el mouse y teclear para operar software humano.
    *   **Recomendación:** Úsalo en entornos controlados (sandboxes) para automatizar pruebas de software o flujos de trabajo de back-office.
*   **`models/gemini-robotics-er-2-preview`**
    *   **Caso de uso:** Procesamiento de telemetría y toma de decisiones físicas espaciales (VLA - Vision-Language-Action).
    *   **Recomendación:** Exclusivo para integración en hardware robótico, drones o gemelos digitales industriales.

### Project Antigravity
*   **`models/antigravity-preview-latest`** / **`09-2026`** / **`05-2026`**
    *   **Caso de uso:** Nodos experimentales de vanguardia (posibles arquitecturas no-Transformer o capacidades de agencia avanzadas).
    *   **Recomendación:** Solo para I+D y pruebas de concepto. Tienen alta probabilidad de cambios abruptos en su comportamiento o estructura de API.

---

## 5. Modelos Abiertos (Gemma)
*   **`models/gemma-4-26b-a4b-it`** / **`models/gemma-4-31b-it`**
    *   **Caso de uso:** Modelos de pesos abiertos (*open weights*) alojados como servicio. `it` significa *Instruct Tuned* (afinado para instrucciones).
    *   **Recomendación:** Úsalos cuando necesites probar prompts que posteriormente planeas ejecutar en tu propio hardware local para evitar el *vendor lock-in*, o cuando busques un estilo de razonamiento más directo y sin tantos filtros como los modelos comerciales.

---

### 💡 Recomendación para tu script actual:
Para el proyecto de consola que creamos anteriormente, te recomiendo configurar la variable `.env` (o directamente el script) para usar **`models/gemini-3.8-flash`** como opción predeterminada. Es el modelo contemporáneo más balanceado entre velocidad deslumbrante, capacidad de razonamiento y costo para un chat de terminal.