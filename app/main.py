from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os


# ============================================================
# LIFESPAN — startup & shutdown events
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validasi environment variables
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        print("⚠️  WARNING: OPENROUTER_API_KEY belum diset!")
        print("   Copy .env.example ke .env dan isi API key-nya.")
    else:
        print(f"✅ OpenRouter API key terdeteksi ({api_key[:8]}...)")

    model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")
    print(f"🤖 Model aktif: {model}")
    print("🚀 Coffee Advisor API siap menerima request!")

    yield

    # Shutdown
    print("👋 Server shutting down...")


# ============================================================
# APP INSTANCE
# ============================================================

app = FastAPI(
    title       = "Coffee Advisor API",
    description = """
## ☕ Coffee Shop Financial Advisor API

API backend untuk fitur chatbot AI advisor keuangan coffee shop Gen Z.

### Alur penggunaan:
1. **POST /api/v1/preprocess** — Submit data bisnis + transaksi harian
2. Simpan `context` dari response di frontend state
3. **POST /api/v1/chat** — Kirim pertanyaan + context untuk dapat saran AI

### Powered by:
- **OpenRouter API** (model gratis: DeepSeek, Llama, Mistral)
- **FastAPI** + **Pydantic v2**
- **Docker** untuk deployment
    """,
    version     = "1.0.0",
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)


# ============================================================
# MIDDLEWARE — HARUS sebelum include_router!
# ============================================================

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


# ============================================================
# ROUTES — setelah middleware
# ============================================================

from app.routes.chat import router as chat_router
app.include_router(chat_router)


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/", tags=["System"])
async def root():
    return {
        "app":     "Coffee Advisor API",
        "version": "1.0.0",
        "docs":    "/docs",
        "health":  "/api/v1/health",
    }
