# 🧠 PROJECT CONTEXT: Polymorphic Realtor Chat (SDUI Bridge)

Este documento es la **Fuente de Verdad** para el propósito, arquitectura y reglas del proyecto.

## 1. Misión (The North Star)
Construir un **Bridge (Puente)** de Server-Driven UI (SDUI) que actúe como una capa de decoración premium para un sistema de IA de bienes raíces. El chat es "Polimórfico": cambia dinámicamente de texto simple a tarjetas de propiedad, mapas, o calculadoras según la intención.

## 2. Arquitectura "Sagrada"
Para mantener la integridad del sistema central (`inference-core`), seguimos estas reglas:

1.  **Bridge Decorador**: El Bridge no es el cerebro. Recibe texto/datos de la IA y les añade la "piel" visual (componentes Lit).
2.  **Auditoría y Verdad**: La tabla `lead_conversations` en la base de datos central es la **Única Fuente de Verdad**. El Bridge no duplica mensajes permanentes.
3.  **Contrato Maestro (Single Source of Truth)**: El archivo [ui.py](file:///srv/web/services/realtor-chat/backend/app/schemas/ui.py) define el esquema de comunicación. Ningún componente se implementa sin estar definido aquí primero.
4.  **Memoria de Dos Capas**:
    *   **DB Central**: Historial y auditoría (Permanente).
    *   **Redis**: Contexto de sesión efímero (Índices de propiedades en pantalla, estado de widgets, cache técnica).

## 3. Tech Stack
*   **Backend**: FastAPI (Python 3.11).
*   **Contratos**: Pydantic (definidos en [ui.py](file:///srv/datasyncsa/services/web/realtor-chat/backend/app/schemas/ui.py)).
*   **Frontend**: Vanilla JS (Orquestador) + **Lit (Google)** para Web Components reactivos.
*   *Persistencia*: Redis (Session Context).
*   **Diseño**: Glassmorphism, Premium Realtor Aesthetic.

## 4. Estructura del Proyecto
*   `backend/app/`: Lógica del Bridge, esquemas Pydantic y gestión de Redis.
*   `frontend/components/`: Widgets visuales (`property-card`, etc.) construidos con Lit.
*   `frontend/core/`: `renderer.js` (Orquestador que traduce JSON a visual).

## 5. Decisiones Técnicas Clave
*   **SDUI Loop**: El backend responde con un array de `components`. El frontend los renderiza dinámicamente.
*   **Mapeo de Índices**: Redis guarda qué propiedad es la "#1", "#2", etc., para permitir al usuario interactuar de forma natural ("dame el mapa de la primera").

## 6. Regresión Reutilizable
- Unit tests backend:
  - Ruta: `services/web/realtor-chat/backend/tests/`
  - Comandos:
    - `docker compose exec -T realtor-api pip install --no-cache-dir -r requirements-dev.txt`
    - `docker compose exec -T realtor-api pytest -q tests`
- Smoke funcional backend:
  - Script: `services/web/realtor-chat/backend/scripts/smoke_bridge.py`
  - Comando:
    - `docker compose exec -T realtor-api python scripts/smoke_bridge.py`
- Referencia rápida:
  - `services/web/realtor-chat/backend/tests/README.md`

-
