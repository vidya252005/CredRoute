from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.routes import router
from app.core.config import settings
from app.core.exceptions import AppError, app_error_handler
from app.db.seed import init_db
from app.core.observability import MetricsMiddleware, configure_logging, prometheus_response


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    init_db()
    yield


app = FastAPI(title=settings.app_name, docs_url="/docs", redoc_url="/redoc", lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)
app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix=settings.api_prefix)
app.include_router(admin_router, prefix=settings.api_prefix)


@app.get("/metrics")
def prometheus_metrics():
    return prometheus_response()
