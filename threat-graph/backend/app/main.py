import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.router import router as api_router
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.errors import AppError
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User

logger = logging.getLogger("threatgraph")


def seed_admin() -> None:
    db = SessionLocal()
    try:
        email = settings.admin_email.lower()
        existing = db.scalar(User.__table__.select().where(User.__table__.c.email == email))
        if existing:
            return
        db.add(
            User(
                email=email,
                username=email.split("@", 1)[0],
                full_name=settings.admin_full_name,
                hashed_password=hash_password(settings.admin_password),
                role=UserRole.ADMIN,
            )
        )
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.graph_path.parent.mkdir(parents=True, exist_ok=True)
    settings.model_path.mkdir(parents=True, exist_ok=True)
    init_db()
    seed_admin()
    yield


app = FastAPI(
    title="ThreatGraph API",
    description="AI-powered cyber attack relationship mapping and prediction system.",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "details": exc.errors()[:50],
            }
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_handler(_: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"error": {"code": "conflict", "message": "Data conflict", "details": str(exc.orig)[:300]}},
    )


@app.exception_handler(SQLAlchemyError)
async def database_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database error")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "database_error", "message": "Database operation failed"}},
    )


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "service": "ThreatGraph", "version": "1.0.0"}


@app.get("/", tags=["system"])
def root() -> dict:
    return {
        "name": "ThreatGraph",
        "description": "AI-Powered Cyber Attack Relationship Mapping and Prediction System",
        "docs": "/docs",
        "api": "/api",
        "health": "/health",
    }


app.include_router(api_router)
