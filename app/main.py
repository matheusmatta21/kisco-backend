from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db import create_db_and_tables
from fastapi.middleware.cors import CORSMiddleware
# from app.routes import auth
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()  # startup
    yield
    
app = FastAPI(title="Malinha KISCO Backend", version="1.0.0", description="API para o backend da Malinha KISCO", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=[settings.FRONTEND_URL], allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"], allow_credentials=True)

# TODO: include routers de auth e users
# app.include_router(auth.router,
#   prefix="/auth")

@app.get("/health")
async def health_check():
    return {"status": "ok"}
