# 🏔️ Ayni Agent System — Terminal Modular & Enrutador Semántico Multi-Agente

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Database](https://img.shields.io/badge/PostgreSQL-Persistencia-blue.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Un orquestador y terminal CLI multi-agente desacoplado, guiado por la filosofía andina del **Ayni** (*reciprocidad y colaboración mutua*). El sistema cuenta con un enrutador semántico inteligente, rotación robusta entre proveedores de LLM (Gemini, Ollama, Manus), soporte multimodal con escáner global de medios y telemetría completa sobre PostgreSQL.

---

## 📐 Arquitectura del Sistema

```mermaid
flowchart TD
    A[Usuario / CLI main.py] --> B[Escáner Global de Medios scan_media_and_select]
    B --> C[AyniOrchestrator]
    C --> D{Proveedor Primario: Gemini}
    D -- Éxito --> E[GeminiSessionManager]
    D -- Fallo / Quota 429 / Bypass --> F[Centro de Contingencia Multi-Agente]
    F --> G[OllamaFallbackManager]
    F --> H[ManusFallbackManager]
    E --> I[DBManager PostgreSQL]
    G --> I
    H --> I
    I --> J[(Base de Datos: interactions, chat_history, errors)]
```

---

## ✨ Características Principales

* **Filosofía Ayni:** Enrutamiento dinámico y colaborativo entre múltiples modelos para garantizar respuesta continua.
* **Semantic Router & Multi-Model Pool:** Intenta la ejecución con el motor primario (Gemini) y rota automáticamente en caso de errores de cuota (`429`), obsolescencia (`404/403`) o bypass manual a contingencias (Ollama, Manus).
* **Escáner Global Multimodal (`media/`):** Detecta y adjunta automáticamente archivos de entrada relevantes según el contexto del prompt.
* **Tool Forcing Universal:** Interceptor basado en Regex para modelos de contingencia sin soportes nativos de Function Calling, simulando llamadas a herramientas (`[GUARDAR_COMO: archivo | carpeta]`).
* **Telemetría y Persistencia PostgreSQL:** Registro estricto de interacciones, tiempos de respuesta (ms), consumo de tokens (input/output), modelos utilizados e historial de chat enriquecido.

---

## 📂 Estructura del Proyecto

```text
.
├── AGENTS.md               # Prompt del Sistema y reglas de negocio del Ayni Agent
├── main.py                 # Punto de entrada de la Terminal Modular (CLI)
├── orchestrator.py         # Orquestador AyniOrchestrator y manejo de contingencias
├── requirements.txt        # Dependencias de Python necesarias
├── media/                  # Directorio de escaneo e interacción de archivos
├── clients/                # Gestores de clientes de IA (Gemini, Ollama, Manus, UI)
└── database/               # Capa de persistencia y gestión de PostgreSQL (DBManager)
```

---

## 🛠️ Requisitos Previos e Instalación

### 1. Clona el repositorio e instala dependencias

```bash
git clone https://github.com/tu-usuario/ayni-agent.git
cd ayni-agent
pip install -r requirements.txt
```

### 2. Configura las Variables de Entorno (`.env`)

Crea un archivo `.env` en la raíz del proyecto:

```env
PRIMARY_PROVIDER=gemini
GEMINI_API_KEY=tu_api_key_de_gemini
DATABASE_URL=postgresql://usuario:password@localhost:5432/ayni_db
OLLAMA_API_URL=http://localhost:11434
TAVILY_API_KEY=tu_api_key_tavily
```

---

## 🚀 Uso del Sistema

Inicia la terminal interactiva desde la raíz del proyecto:

```bash
python main.py
```

### Comandos y Flujo de Trabajo

* **Interacción Normal:** Escribe tu consulta directamente en la terminal.
* **Adjuntar Archivos:** Coloca archivos en la carpeta `media/`. El escáner preseleccionará los archivos mencionados o requeridos en tu prompt.
* **Salir de la Sesión:** Escribe `salir`, `quit` o `exit`.

---

## 📊 Telemetría y Base de Datos

Cada consulta ejecutada registra métricas clave en PostgreSQL:

| Campo | Descripción |
| :--- | :--- |
| `session_id` | Identificador de la sesión activa |
| `provider` / `model_used` | Motor y modelo exacto que procesó la respuesta |
| `input_tokens` / `output_tokens` | Conteo de tokens consumidos |
| `response_time_ms` | Latencia total de la ejecución en milisegundos |
| `error_data` | Logs detallados en caso de haber activado contingencias |

---

## 📄 Licencia

Este proyecto está bajo la Licencia **MIT**. Consulta el archivo `LICENSE` para más detalles.
