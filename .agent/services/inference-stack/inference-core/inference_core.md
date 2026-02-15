# Service Spec: Inference Core

## 1. Identidad
- **Nombre:** Inference Core
- **Contenedor:** `inference-core` (Docker Compose Service Name)
- **Despliegue:** Docker Compose Stack (Network `internal_network`)
- **Tecnología:** FastAPI + LangChain

## 2. Propósito y Funciones Clave
Es el motor central de inferencia y el punto de contacto para las aplicaciones cliente.
- **Resolución de Intenciones:** Actúa como router para dirigir la consulta al agente o flujo adecuado.
- **Orquestación RAG:** Consulta al `Semantic Adapter` para obtener contexto y construye el prompt final.
- **Acceso a Datos:** Consulta tanto el Vector Store (vía Semantic Adapter) como bases de datos relacionales para datos estructurados.
- **Lógica de Negocio:** Aplica las reglas de decisión antes de entregar la respuesta.

## 3. Responsabilidad (Scope Estricto)
El Inference Core es responsable de:
1. Recibir consultas del usuario (Web, WhatsApp, etc.).
2. Gestionar la memoria de la conversación (si aplica).
3. Construir prompts dinámicos.
4. Llamar a los modelos de lenguaje (LLM).
5. Entregar respuestas en el formato contractual requerido por el cliente.

**PROHIBIDO (No implementar aquí):**
- Ingesta o limpieza de datos masivos (ETL).
- Scraping o parsing de documentos originales.
- Generación o actualización de embeddings en lote (Batch).

## 4. Flujo de Operación
1. **Entrada:** Recibe `query`, `user_context` y `session_id`.
2. **Retrieval:** Solicita fragmentos relevantes al `semantic-adapter` (http://semantic-adapter:8000).
3. **Augmentation:** Inserta el contexto en el template del prompt.
4. **Generation:** Llama al LLM (Gemini/OpenAI).
5. **Post-processing:** Formatea la respuesta según la necesidad del canal de salida.

## 6. Regresión Reutilizable
- Unit tests:
  - Ruta: `services/inference-stack/inference-core/tests/`
  - Comandos:
    - `docker compose exec -T inference-core pip install --no-cache-dir -r requirements-dev.txt`
    - `docker compose exec -T inference-core pytest -q tests`
- Smoke funcional:
  - Script: `services/inference-stack/inference-core/tests/smoke/test_smoke_chat.py`
  - Comando:
    - `docker compose exec -T inference-core python tests/smoke/test_smoke_chat.py`
- Referencia rápida:
  - `services/inference-stack/inference-core/tests/README.md`
