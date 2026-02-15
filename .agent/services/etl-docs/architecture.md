# 🏗️ Módulo ETL-DOCS: Base de Conocimiento Documental

Este módulo implementa el pipeline de ingesta, procesamiento y vectorización de documentos (PDFs) para la Base de Conocimiento del Agente.

## 🌟 Características Clave
*   **Asíncrono (Redis Queue)**: Worker procesa archivos pesados.
*   **Híbrido (Texto/OCR)**: Fallback automático a Tesseract si el PDF es imagen.
*   **Idempotente (SHA-256)**: Evita duplicados de contenido.
*   **Vectorización**: Google Gemini (`text-embedding-004`).

## 📂 Estructura y Conectividad
- **Service URL**: Definida externamente por `ETL_SERVICE_URL` (ej. `https://etl-docs.midominio.com`).
- `/shared/file_manager.py`: Almacenamiento físico en `/app/data/storage/documents/`.
- `/shared/vector_store.py`: Gestión de embeddings y Postgres/pgvector.
- `/ETL_DOCS/processor.py`: Lógica de extracción Texto/OCR.

## 📡 API Endpoints

Todos los endpoints tienen el prefijo base `/documents`.

### 1. Ingesta de Documentos
`POST /upload`
- **Descripción**: Recibe un PDF y lo encola para procesamiento asíncrono mediante Redis Queue (RQ).
- **Form Data**:
    - `file`: Archivo binario (MIME type obligatoriamente `application/pdf`).
    - `client_id`: UUID del cliente propietario del recurso.
    - `content_id`: (Opcional) Identificador único para el documento. Si no se provee, se genera un UUID.
    - `access_level` (Form): `private` (default) o `shared`.
    - `category` (Form): `knowledge_base` (default) o string libre.
- **Respuesta (202 Accepted)**:
    ```json
    {
        "status": "QUEUED",
        "job_id": "job_doc_...",
        "content_id": "doc_...",
        "filename": "contrato.pdf",
        "queue_position": 1
    }
    ```
- **Errores**:
    - `409 Conflict`: Si el archivo ya existe (físicamente o en DB).

### 2. Listado de Documentos (Poblar Grid)
`GET /list/{client_id}`
- **Descripción**: Devuelve todos los documentos registrados para un cliente, ideal para mostrar en un Grid/Tabla.
- **Respuesta**:
    ```json
    {
        "status": "success",
        "client_id": "...",
        "count": 1,
        "documents": [
            {
                "id": 1,
                "filename": "contrato.pdf",
                "sync_status": "SYNCED",
                "content_id": "doc_...",
                "access_level": "private",
                "category": "knowledge_base",
                "created_at": "..."
            }
        ]
    }
    ```

### 3. Monitoreo de Procesamiento
`GET /jobs/{job_id}`
- **Descripción**: Consulta el estado de la tarea en cola (polling).
- **Estados posibles**: `queued`, `started`, `finished`, `failed`.

### 4. Gestión y Limpieza
`DELETE /{client_id}/{content_id}`
- **Descripción**: Eliminación granular de un documento específico. Borra el archivo físico, el registro en `ai_knowledge_documents` y los vectores en `ai_vectors`.
    
`DELETE /client/{client_id}`
- **Descripción**: Purga total de recursos de un cliente. (Baja de servicio).

## 💡 Notas para Integración (UI Neighbor)
1. **Poblado de Grid**: Usa `GET /list/{client_id}` para mostrar la tabla inicial o realiza una consulta directa a la tabla `ai_knowledge_documents` si tienes acceso a la BD.
2. **Carga Continua**: Tras un `POST /upload`, usa el `job_id` para hacer polling en `/jobs/{job_id}` y actualizar el estado de esa fila específica en la UI.
3. **Generación de IDs (content_id)**: Se recomienda que la UI genere su propio UUID para cada documento. Esto permite una UX inmediata y evita duplicados.

**Ejemplo en JavaScript (Frontend):**
```javascript
const content_id = `doc_${crypto.randomUUID()}`;
```

**Ejemplo en Python (Backend):**
```python
import uuid
content_id = f"doc_{uuid.uuid4()}"
```

4. **Persistencia**: El `content_id` es el vínculo entre tus registros y el conocimiento vectorial. Úsalo como llave de unión entre tu base de datos y el servicio ETL.
