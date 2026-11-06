"""
AnonDoc main application entrypoint.
FastAPI web application with REST API and web UI.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from anondoc.application.job_manager import JobLimitReached
from anondoc.application.use_cases import JobBusy, JobStateError, VerificationFailed
from anondoc.config import AppConfig
from anondoc.infrastructure.sandbox.runner import ServerBusy, WorkerError
from anondoc.infrastructure.security.inspector import DocumentRejected
from anondoc.presentation.api.middleware import BodySizeLimitMiddleware, security_middleware
from anondoc.presentation.api.routes import router as api_router
from anondoc.presentation.api.routes import use_cases

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("anondoc.app")

WEB_DIR = Path(__file__).parent / "presentation" / "web"


async def _purge_loop():
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(use_cases.purge_expired)
        except Exception:  # noqa: BLE001
            log.error("purge_failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    AppConfig.ensure_directories()
    # Jobs live in memory only, so anything left on disk from a previous run is an orphan.
    use_cases.storage.purge_expired_jobs(0)
    task = asyncio.create_task(_purge_loop())
    yield
    task.cancel()
    use_cases.storage.purge_expired_jobs(0)


app = FastAPI(
    title=AppConfig.APP_NAME,
    version=AppConfig.VERSION,
    description="Motor independiente de detección y anonimización de información personal en documentos PDF y DOCX.",
    lifespan=lifespan,
    docs_url="/docs" if AppConfig.ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if AppConfig.ENABLE_DOCS else None,
)

if AppConfig.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=AppConfig.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
app.middleware("http")(security_middleware)
app.add_middleware(BodySizeLimitMiddleware)


def _error(status_code: int, code: str, message: str, headers: dict = None) -> JSONResponse:
    return JSONResponse({"detail": message, "code": code}, status_code=status_code, headers=headers)


@app.exception_handler(DocumentRejected)
async def _rejected(_: Request, exc: DocumentRejected):
    return _error(413 if exc.code == "file_too_large" else 400, exc.code, exc.message)


@app.exception_handler(WorkerError)
async def _worker_error(_: Request, exc: WorkerError):
    client_errors = {"timeout": 422, "resource_limit": 422, "processing_error": 422}
    status_code = client_errors.get(exc.code, 400)
    return _error(status_code, exc.code, exc.message)


@app.exception_handler(ServerBusy)
async def _busy(_: Request, __: ServerBusy):
    return _error(503, "server_busy", "El servidor está ocupado. Intente de nuevo en unos segundos.", {"Retry-After": "10"})


@app.exception_handler(JobLimitReached)
async def _job_limit(_: Request, __: JobLimitReached):
    return _error(503, "capacity", "Capacidad máxima alcanzada. Intente más tarde.", {"Retry-After": "60"})


@app.exception_handler(JobBusy)
async def _job_busy(_: Request, __: JobBusy):
    return _error(409, "job_busy", "Hay otra operación en curso para este trabajo.")


@app.exception_handler(JobStateError)
async def _job_state(_: Request, exc: JobStateError):
    return _error(409, "invalid_state", str(exc))


@app.exception_handler(VerificationFailed)
async def _verification(_: Request, __: VerificationFailed):
    return _error(
        422, "verification_failed",
        "La verificación posterior a la anonimización falló: el documento no se entrega. "
        "Revise las entidades seleccionadas o pruebe con otro documento.",
    )


@app.exception_handler(RequestValidationError)
async def _validation(_: Request, exc: RequestValidationError):
    # Field locations only: the default handler echoes the submitted input.
    fields = [".".join(str(p) for p in e.get("loc", ())) for e in exc.errors()]
    return JSONResponse({"detail": "Solicitud inválida.", "code": "validation_error", "fields": fields}, status_code=422)


@app.exception_handler(StarletteHTTPException)
async def _http(_: Request, exc: StarletteHTTPException):
    return JSONResponse({"detail": exc.detail, "code": "http_error"}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception):
    # Class name only: exception messages may contain document-derived data.
    log.error("unhandled_error type=%s", type(exc).__name__)
    return _error(500, "internal_error", "Error interno del servidor.")


app.include_router(api_router)
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return HTMLResponse(content=(WEB_DIR / "templates" / "index.html").read_text(encoding="utf-8"))


def run():
    import uvicorn
    uvicorn.run("anondoc.main:app", host=AppConfig.HOST, port=AppConfig.PORT, reload=AppConfig.DEBUG)


if __name__ == "__main__":
    run()
