from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import settings
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
import logging

# Import Feature Modules
from app.dashboards.base_dash.router import router as base_dash_router
from app.dashboards.manager_workspace.router import router as manager_workspace_router
from app.dashboards.seller_workspace.router import router as seller_workspace_router
from app.modules.clients.router import router as clients_router
from app.modules.countries.router import router as countries_router
from app.modules.prompts.router import router as prompts_router
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.roles.router import router as roles_router
from app.modules.contacts.router import router as contacts_router
from app.modules.leads.router import router as leads_router
from app.modules.campaigns.router import router as campaigns_router
from app.modules.ai_library.router import router as ai_library_router
from app.modules.system_public_docs.router import router as system_public_docs_router
from app.modules.grid_presets.router import router as grid_presets_router

app = FastAPI(title="Web IAFirst Operational API")
logger = logging.getLogger(__name__)

cors_origins = settings.cors_allow_origins or ["*"]
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": "Request Validation Error"},
    )

@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request, exc):
    logger.exception("Response contract validation failed", exc_info=exc)
    return JSONResponse(
        status_code=500, 
        content={"detail": "Response Contract Violation"},
    )

@app.get("/health")
async def health_check():
    return {"status": "operational", "version": "1.0"}

# Include Feature Routers
app.include_router(base_dash_router, tags=["Dashboard (Base)"]) # Root prefix for app-init
app.include_router(manager_workspace_router, prefix="/dashboard")
app.include_router(seller_workspace_router, prefix="/dashboard")
app.include_router(leads_router, prefix="/leads", tags=["Leads Operations"])
app.include_router(campaigns_router, prefix="/campaigns", tags=["Campaigns Operations"])
app.include_router(ai_library_router, prefix="/ai-library", tags=["AI Library Management"])
app.include_router(system_public_docs_router)

app.include_router(clients_router, tags=["Clients"])
app.include_router(countries_router, tags=["Countries (System)"])
app.include_router(prompts_router, tags=["AI Prompts"])
app.include_router(auth_router) # Tags are defined inside the router
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(contacts_router, tags=["Contacts"])
app.include_router(grid_presets_router)
