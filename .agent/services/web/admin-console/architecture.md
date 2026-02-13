# admin-console - Architectural Guidelines

This document serves as the **Single Source of Truth** for architectural decisions and code standards.

## 1. Backend Architecture: Feature-Based Modules
We reject Layer-Based architecture (Services/Controllers/Routes separated) in favor of **Feature-Based Architecture**.

**Rule:** Every domain feature must reside in its own self-contained directory within `backend/app/modules/`.

### Structure
```
backend/app/modules/
└── [feature_name]/       <-- e.g., 'clients', 'dashboard'
    ├── router.py         <-- Defines Endpoints. Returns UI Schema.
    ├── service.py        <-- (Optional) Business Logic & Data Access.
    └── schemas.py        <-- (Optional) Pydantic Models specific to this feature.
```

### The Role of `main.py`
*   **Strictly Minimal**: `main.py` MUST only initialize the FastAPI app, configure Middleware (CORS), and `include_router` from modules.
*   **No Logic**: Never write business logic or endpoints directly in `main.py`.

## 2. Server-Driven UI (SDUI)
The Frontend is a "Dumb Renderer". The Backend is the "Brain".

**Rule:** The Frontend never decides *what* to render based on URL. It asks the Backend for the layout.

### Flow
1.  **Frontend Navigation**: User clicks a link (e.g., `/clients`).
2.  **Interceptor**: `main.js` intercepts the click.
3.  **Fetch**: Calls Backend API with the same path (e.g., `GET API/clients`).
4.  **Response**: Backend returns a JSON describing components (Grid, Cards, Typography).
5.  **Render**: `main.js` dynamically builds the HTML based on the JSON.

**Implication**: To create a new page, you create a Backend Endpoint. You do NOT touch Frontend Routing code.

## 3. Frontend Components & Velzon Theme
We use the **Official Velzon** assets and structure.

**Visual Consistency Rules:**
1.  **Native Assets**: Use `app.min.css`, `bootstrap.min.css`, and `icons.min.css` from the theme. avoid custom CSS unless critical.
2.  **DOM Structure**: Components (`AppShell.js`, `Sidebar.js`) MUST output HTML that matches the official Velzon `index.html` structure exactly.
3.  **Component Directory**:
    *   `components/layouts/`: Structural (Sidebar, Navbar).
    *   `components/forms/`: Inputs, Buttons.
    *   `components/grids/`: Tables, Lists.
    *   `components/cards/`: Metric Cards, Profile Cards.

## 4. Operational Workflows
*   **Adding a Feature**:
    1.  Create `backend/app/modules/[new_feature]/router.py`.
    2.  Define the UI Structure in the endpoint.
    3.  Register the router in `backend/app/main.py`.
    4.  Add the link to the Sidebar menu (in `dashboard/router.py`).

## 5. Security, Authentication & RBAC
In a Feature-Based Architecture, security should be applied at the **Router Level** or **Global/Include Level**, not inside every endpoint manually.

### Pattern A: Module-Level Security (Preferred for Auth)
Apply dependencies when including the router in `main.py`. This ensures *all* endpoints in that module are protected.

```python
# main.py
from app.auth.dependencies import get_current_user, require_role

app.include_router(
    clients_router, 
    prefix="/clients", 
    dependencies=[Depends(get_current_user), Depends(require_role("admin"))]
)
```

### Pattern B: Granular Security (Preferred for specific endpoints)
Apply dependencies directly in the module's `router.py` for mixed-access modules.

```python
# modules/dashboard/router.py
@router.get("/sensitive-data", dependencies=[Depends(require_role("superadmin"))])
async def get_sensitive_data():
    ...
```

### Pattern C: Menu/Router Synchronization (CRITICAL)
**Security Rule**: You must NEVER hide a menu item without also securing its target route.
*   **IF** an entry is restricted in `menus.py` (e.g. only for "admin"),
*   **THEN** the target `router.py` **MUST** have an equivalent `Depends(RoleChecker(["admin"]))` guard.
*   *Auditing*: A button visible to a user but blocked by the backend is a bad UX. A button hidden but accessible via API is a Security Vulnerability.

### Middleware
Global middleware (CORS, Logging) belongs in `main.py`. Feature-specific middleware should be implemented as a Dependency.

## 6. Authentication Provider & Database Schema
**Strategic Decision**: Greenfield Implementation.

**Validator & Manager**: **`FastAPI Users`** (Library).


## 7. Generic CRUD (SDUI Protocol)
To avoid writing repetitive Javascript for every module, we follow a strict **Metadata-Driven** approach.

### 7.1 Backend Responsibility
The Router must return not just data, but the **Form Schema**:
```python
"form_schema": [
    {"name": "name", "label": "Full Name", "type": "text", "required": True},
    {"name": "role", "label": "Role", "type": "badge", "required": False}
]
```

### 7.2 Frontend Responsibility
1.  **Hydration**: `main.js` reads `data-schema` from the Grid DOM during hydration.
2.  **Generic Modals**: `openGenericModal(schema)` renders the form on-the-fly.
3.  **Generic Actions**: Buttons use `onclick="window.handleGenericAction(this)"`.

### 7.3 Dual-Layer Validation Strategy
To ensure both UX and Security, we implement validation in two synchronized layers:

1.  **Likely UX (Frontend - SDUI)**:
    *   Defined in `router.py` within `form_schema`.
    *   Attributes: `min_length`, `max_length`, `pattern`.
    *   **Goal**: Prevent user frustration via browser-native enforcement.

    ```python
    {"name": "iso", "type": "text", "min_length": 2, "max_length": 3}
    ```

2.  **Strict Security (Backend - Pydantic)**:
    *   Defined in `schemas.py`.
    *   **Goal**: Ensure data integrity and prevent attacks.
    *   **CRITICAL**: Must match or be stricter than SDUI rules.

    ```python
    iso: str = Field(..., min_length=2, max_length=3)
    ```

**Handling Errors**: The Frontend (`main.js`) is programmed to catch `422 Unprocessable Entity` responses and display specific field errors in the SweetAlert modal.

## 8. Configuration Management
Due to browser security protocols, the Frontend **cannot** directly access server-side environment variables (`.env`).

### 8.1 Strategy: Decoupled Configuration
We use a **Decoupled Strategy** to manage configuration:
1.  **Backend**: Reads directly from `.env` using `python-dotenv`.
2.  **Frontend**: Reads from `frontend/config.js`, which exposes a global `window.AppConfig` object.

### 8.2 Maintenance
**Manual Sync Required**: If you change `API_BASE_URL` in `.env`, you **MUST** update `frontend/config.js` to match.
*   *Future Optimization*: This can be automated via CI/CD pipelines or Docker entrypoints that generate `config.js` at runtime based on environment variables.

## 9. Deployment & Environment Context
This project runs within a structured Docker environment. It is CRITICAL to execute commands (e.g., Python scripts, Database migrations) within the appropriate container.

### 9.1 Container Service Map
(Reference: `ai_context/docker-compose.reference.yml`)

##ask to ia to complete this section

### 9.2 Legacy Authentication Schema
For Phase 1 Authentication integration, we connect to the existing User/Tenant tables located in the same database.

**Table: `lead_users`**
*   **Primary Key**: `id` (UUID)
*   **Credentials**: `email`, `password` (Hashed), `username` (alias `name`?)
*   **Status**: `available_status`, `can_receive_leads`

**Table: `lead_client_user`** (Pivot)
*   User-to-Tenant relationship table.
*   **Columns**: `id`, `user_id`, `client_id`

**Note**: Do NOT rely on local `venv` in the host machine as it may lack dependencies. Always use the Container.
