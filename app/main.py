import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, engine

import app.models

from app.routes.auth import router as auth_router
from app.routes.teacher import router as teacher_router
from app.routes.parent import router as parent_router


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


# =========================================================
# CORS
# =========================================================

allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.1.119:3000",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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