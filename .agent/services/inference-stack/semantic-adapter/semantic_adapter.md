# Service Spec: Semantic Adapter

## 1. Identidad
- **Nombre:** Semantic Adapter
- **Contenedor:** `semantic-adapter` (Docker Compose Service Name)
- **Despliegue:** Docker Compose Stack (Network `internal_network`)
- **Tecnología:** FastAPI + Python

## 2. Propósito y Funciones Clave
Actúa como la capa de inteligencia de datos y persistencia vectorial del stack.
- **Generación de Embeddings:** Conecta con OpenAI, Gemini o modelos locales.
- **Gestión de Persistencias:** Administra PostgreSQL + pgvector con índices **HNSW**.
- **Control de Idempotencia:** Uso de hashes únicos para evitar duplicidad.
- **Búsqueda Semántica:** Ejecuta consultas de similitud de coseno para el Inference Core.

## 3. Responsabilidad (Scope Estricto)
El Semantic Adapter es responsable de:
1. Tomar contenido ya normalizado (canónico).
2. Aplicar reglas explícitas de vectorización.
3. Generar chunks semánticos.
4. Calcular embeddings.
5. Persistir vectores y metadata.
6. Gestionar el versionado semántico por cliente.

**PROHIBIDO (No implementar aquí):**
- Ingesta de datos crudos.
- Mapeos estructurales (esto es del ETL Adapter).
- Inferencia / Chat directo con el usuario final.
- Orquestación o Scheduling.