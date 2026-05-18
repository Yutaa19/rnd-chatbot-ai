from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("⚠️ WARNING: OPENROUTER_API_KEY environment variable is not set. LLM services will not work.")
    else:
        print("✅ OPENROUTER_API_KEY found. LLM services are ready to use.")
    
    model = os.getenv("OPENROUTER_MODEL", "")
    if model:
        print("✅ OPENROUTER_MODEL aman...")
    else:
        print("⚠️ WARNING: OPENROUTER_MODEL environment variable is not set. Default model will be used.")
    yield

    print("🔄 Shutting down API...")

app = FastAPI(
    title="coffe shop chatbot advisor API",
    description="API untuk chatbot advisor yang memberikan rekomendasi bisnis berdasarkan data transaksi harian.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

 # MIDDLEWARE 

# Baca allowed origins dari env, default ke semua (untuk development)
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = (
    allowed_origins_env.split(",")
    if allowed_origins_env != "*"
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = allowed_origins,   # ✅ http bukan https untuk localhost
    allow_credentials = True,
    allow_methods     = ["GET", "POST"],
    allow_headers     = ["*"],
)

from app.routes import chat
app.include_router(chat.router)


@app.get("/", tags=["System"])
async def root():
    return {
        "app":     "Coffee Advisor API",
        "version": "1.0.0",
        "docs":    "/docs",
        "health":  "/api/v1/health",
    }