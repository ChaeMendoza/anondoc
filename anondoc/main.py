"""
AnonDoc Main Application Entrypoint.
FastAPI web application with REST API and Modern UI Dashboard.
"""
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from anondoc.config import AppConfig
from anondoc.presentation.api.routes import router as api_router
from anondoc.infrastructure.storage.temp_storage import SecureStorageService

storage_service = SecureStorageService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure base directories
    AppConfig.ensure_directories()
    # Initial cleanup of stale files
    storage_service.purge_expired_jobs()
    yield
    # Shutdown: final sweep
    storage_service.purge_expired_jobs()

app = FastAPI(
    title=AppConfig.APP_NAME,
    version=AppConfig.VERSION,
    description="Motor independiente de detección y anonimización de información personal en documentos PDF y DOCX.",
    lifespan=lifespan
)

# CORS Seguro
app.add_middleware(
    CORSMiddleware,
    allow_origins=AppConfig.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Registrar API
app.include_router(api_router)

# Archivos estáticos y Templates
static_dir = Path(__file__).parent / "presentation" / "web" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    template_path = Path(__file__).parent / "presentation" / "web" / "templates" / "index.html"
    if template_path.exists():
        return HTMLResponse(content=template_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>AnonDoc API está en línea. Consulte /docs para Swagger.</h1>")

def run():
    import uvicorn
    uvicorn.run("anondoc.main:app", host=AppConfig.HOST, port=AppConfig.PORT, reload=AppConfig.DEBUG)

if __name__ == "__main__":
    run()
