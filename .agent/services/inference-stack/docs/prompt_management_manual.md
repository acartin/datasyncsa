# Manual de Administración de Prompts

Este documento describe el funcionamiento, arquitectura y gestión del sistema de prompts dinámicos para el servicio de `Inference Core`.

## 1. Visión General

El sistema de chat utiliza un mecanismo de prompts dinámicos que permite personalizar el comportamiento del bot por cliente (multi-tenant) sin necesidad de redeplegar el código. Los prompts se almacenan en la base de datos y se cargan en tiempo de ejecución.

**Servicio Responsable:** `inference-core` (Docker Backend)

## 2. Arquitectura de Datos

Los prompts se almacenan en la tabla `lead_ai_prompts` dentro de la base de datos PostgreSQL.

### Schema de la Tabla `lead_ai_prompts`

| Columna       | Tipo      | Descripción |
|---------------|-----------|-------------|
| `id`          | UUID/Int  | Identificador único del registro. |
| `client_id`   | TEXT      | ID del cliente (Tenant). Si es `NULL`, se considera un prompt global por defecto. |
| `slug`        | TEXT      | Identificador lógico del prompt (ej. `primary_chat`). |
| `prompt_text` | TEXT      | El contenido del prompt del sistema. |
| `is_active`   | BOOLEAN   | Indica si el prompt está habilitado. |
| `created_at`  | TIMESTAMP | Fecha de creación. |
| `updated_at`  | TIMESTAMP | Fecha de última actualización. |

> **Nota**: El schema exacto puede variar ligeramente dependiendo de las migraciones ejecutadas, pero estas son las columnas funcionales utilizadas por el servicio.

## 3. Lógica de Selección del Prompt

El servicio (`ConversationRepository`) sigue una jerarquía estricta para determinar qué prompt utilizar para una conversación dada:

1. **Prompt Específico de Cliente**: 
   - Busca en `lead_ai_prompts` donde `client_id` coincida con el cliente de la solicitud y `slug` sea el solicitado (por defecto `primary_chat`).
   - Debe tener `is_active = true`.

2. **Prompt Global (Default)**:
   - Si no se encuentra uno específico, busca un registro donde `client_id` sea `NULL` y el `slug` coincida.
   - Debe tener `is_active = true`.

3. **Fallback de Código**:
   - Si no existe ningún registro en base de datos, se utiliza un prompt de emergencia hardcodeado:
     > "Eres un asistente técnico. Responde basándote exclusivamente en el contexto:\n\n{context_text}"

## 4. Gestión y Administración

Actualmente, no existe una interfaz gráfica (UI) ni endpoints API para la administración de prompts. La gestión se realiza directamente vía SQL.

### Crear un Prompt Global (Default)

```sql
INSERT INTO lead_ai_prompts (client_id, slug, prompt_text, is_active, created_at, updated_at)
VALUES (
    NULL, 
    'primary_chat', 
    'Eres un asistente útil y amable. Utiliza el siguiente contexto para responder:\n\n{context_text}', 
    true, 
    NOW(), 
    NOW()
);
```

### Crear un Prompt Específico para un Cliente

```sql
INSERT INTO lead_ai_prompts (client_id, slug, prompt_text, is_active, created_at, updated_at)
VALUES (
    'client_12345', 
    'primary_chat', 
    'Eres el asistente virtual de la empresa X. Responde de manera formal.\n\nContexto:\n{context_text}', 
    true, 
    NOW(), 
    NOW()
);
```

### Modificar un Prompt

```sql
UPDATE lead_ai_prompts 
SET prompt_text = 'Nuevo texto del prompt...', updated_at = NOW()
WHERE client_id = 'client_12345' AND slug = 'primary_chat';
```

## 5. Variables y Plantillas

El sistema soporta la inyección dinámica de variables dentro del texto del prompt. Es **obligatorio** incluir la variable de contexto si se desea que el bot utilice la información recuperada de la base de conocimientos (RAG).

### Variables Disponibles

- `{context_text}`: Contiene los fragmentos de texto recuperados de la búsqueda semántica, formateados como fuentes.

### Ejemplo de Uso

```text
Actúa como un agente de soporte de nivel 1.
Tu objetivo es responder preguntas sobre el manual de usuario.

Si la respuesta no está en el contexto, di que no lo sabes.

Contexto recuperado:
{context_text}

Pregunta del usuario: {input}
```

> **Importante**: El marcador `{input}` es manejado automáticamente por LangChain al concatenar el historial, pero el system prompt debe estar preparado para anteceder esa interacción. El código actual inyecta `{context_text}` antes de enviar el system message a LangChain.
