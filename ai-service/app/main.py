from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Cek API key OpenRouter ─────────────────────────────────────────────
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("⚠️  WARNING: OPENROUTER_API_KEY tidak di-set. LLM tidak akan berfungsi.")
    else:
        print("✅ OPENROUTER_API_KEY ditemukan.")

    model_env = os.getenv("OPENROUTER_MODEL", "")
    if model_env:
        print("✅ OPENROUTER_MODEL terkonfigurasi.")
    else:
        print("⚠️  WARNING: OPENROUTER_MODEL tidak di-set. Default model akan digunakan.")

    # ── Load LSTM model & scaler ───────────────────────────────────────────
    # Import di dalam lifespan agar error saat startup terlihat jelas
    from app.services.inference_service import load_model_and_scaler
    try:
        load_model_and_scaler()
    except FileNotFoundError as e:
        # Tidak crash app — tapi forecast akan fallback ke logik dummy
        print(f"⚠️  WARNING: {e}")
        print("⚠️  Forecast LSTM tidak aktif. Fallback ke logik heuristik.")

    yield

    print("🔄 Shutting down API...")


app = FastAPI(
    title="Caffeinance API",
    description="API untuk chatbot advisor keuangan coffee shop dengan prediksi cashflow LSTM.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# ── CORS Middleware ────────────────────────────────────────────────────────────
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = (
    allowed_origins_env.split(",")
    if allowed_origins_env != "*"
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = allowed_origins,
    allow_credentials = True,
    allow_methods     = ["GET", "POST"],
    allow_headers     = ["*"],
)

from app.routes import chat
app.include_router(chat.router)


@app.get("/", tags=["System"])
async def root():
    return {
        "app":     "Caffeinance API",
        "version": "1.0.0",
        "docs":    "/docs",
        "health":  "/api/v1/health",
    }