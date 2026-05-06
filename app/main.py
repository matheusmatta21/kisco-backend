from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db import create_db_and_tables
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, users
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()  # startup
    yield


app = FastAPI(
    title="Malinha KISCO Backend",
    version="1.0.0",
    description="API para o backend da Malinha KISCO",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(auth.router, prefix="/auth")
app.include_router(users.router, prefix="/users")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
