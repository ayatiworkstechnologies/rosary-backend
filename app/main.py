import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, engine

import app.models

from app.routes.auth import router as auth_router
from app.routes.teacher import router as teacher_router
from app.routes.parent import router as parent_router

from app.api.v1.admin.dashboard import router as admin_dashboard_router
from app.api.v1.admin.classes import (
    router as admin_classes_router,
)
from app.api.v1.admin.students import (
    router as admin_students_router,
)
from app.api.v1.admin.parent_links import (
    router as admin_parent_links_router,
)
from app.api.v1.admin.teachers import (
    router as admin_teachers_router,
)
from app.api.v1.admin.circulars import (
    router as admin_circulars_router,
)
from app.api.v1.admin.school_events import (
    router as admin_school_events_router,
)
from app.api.v1.admin.fees import (
    router as admin_fees_router,
)
from app.api.v1.admin.downloads import router as admin_downloads_router

from app.api.v1.admin.exams import (
    router as admin_exams_router,
)
from app.api.v1.admin.results import (
    router as admin_results_router,
)
from app.api.v1.admin.exam_schedules import (
    router as admin_exam_schedules_router,
)
from app.api.v1.admin.users import (
    router as admin_users_router,
)
from app.api.v1.admin.parents import (
    router as admin_parents_router,
)
# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


# =========================================================
# CREATE DATABASE TABLES
# =========================================================

Base.metadata.create_all(bind=engine)


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="Rosary School Portal API",
    description="Backend API for Rosary Teacher and Parent Portal",
    version="1.0.0",
)


@app.middleware("http")
async def normalize_admin_api_path(request, call_next):
    """Accept the admin URL forms used by older and newer portal builds.

    The admin routers are mounted under ``/api/v1``. Some deployed frontend
    builds use ``/api`` or omit the API prefix entirely, which otherwise
    produces a misleading 404 before the request reaches the handler.
    """
    path = request.scope["path"]
    if path == "/admin" or path.startswith("/admin/"):
        request.scope["path"] = "/api/v1" + path
    elif path == "/api/admin" or path.startswith("/api/admin/"):
        request.scope["path"] = "/api/v1" + path[len("/api"):]
    return await call_next(request)


# =========================================================
# CORS
# =========================================================

allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.1.119:3000",
    # Vite and other modern frontend dev servers commonly use 5173.
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.1.119:5173",
]

# Allow deployments to add their frontend origin without changing code. Keep
# the explicit defaults because credentials are enabled and '*' is invalid in
# that mode.
configured_origins = os.getenv("CORS_ORIGINS", "")
if configured_origins:
    allowed_origins.extend(
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    )
allowed_origins = list(dict.fromkeys(allowed_origins))


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Download records contain URLs under /uploads. Mounting the directory keeps
# the URL returned by both admin and parent download APIs usable by the UI.
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "message": "Rosary School Portal API",
        "status": "running",
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():
    try:

        with engine.connect() as connection:
            connection.execute(
                text("SELECT 1")
            )

        return {
            "status": "healthy",
            "database": "connected",
        }

    except SQLAlchemyError as error:

        logger.exception(
            "Database health check failed"
        )

        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(error),
        }


# =========================================================
# ROUTERS
# =========================================================

app.include_router(auth_router)
app.include_router(teacher_router)
app.include_router(parent_router)

app.include_router(
    admin_dashboard_router,
    prefix="/api/v1"
)
app.include_router(
    admin_classes_router,
    prefix="/api/v1",
)
app.include_router(
    admin_students_router,
    prefix="/api/v1",
)
app.include_router(
    admin_parent_links_router,
    prefix="/api/v1",
)
app.include_router(
    admin_teachers_router,
    prefix="/api/v1",
)

app.include_router(
    admin_circulars_router,
    prefix="/api/v1",
)
app.include_router(
    admin_school_events_router,
    prefix="/api/v1",
)
app.include_router(
    admin_fees_router,
    prefix="/api/v1",
)
app.include_router(admin_downloads_router)
app.include_router(
    admin_exams_router
)
app.include_router(
    admin_results_router
)
app.include_router(
    admin_exam_schedules_router
)
app.include_router(
    admin_users_router
)
app.include_router(
    admin_parents_router,
    prefix="/api/v1",
)