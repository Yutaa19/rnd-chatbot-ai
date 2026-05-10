import traceback
from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    ChatRequest, ChatResponse,
    PreprocessRequest, PreprocessResponse,
)
from app.services.llm_service import generate_response
from app.services.preprocess_service import preprocess_transactions

router = APIRouter(prefix="/api/v1", tags=["Coffee Advisor"])


# ============================================================
# POST /api/v1/chat
# Endpoint utama chatbot — frontend kirim message + context
# ============================================================

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat dengan AI Advisor",
    description="""
    Kirim pertanyaan user beserta konteks prediksi ML.
    Context idealnya digenerate dari endpoint /preprocess terlebih dahulu,
    lalu disimpan di frontend state dan dikirim bersama setiap pertanyaan.
    """
)
async def chat(request: ChatRequest):
    try:
        result = await generate_response(
            message=request.message,
            context=request.context,
        )
        return ChatResponse(
            reply       = result["reply"],
            model_used  = result.get("model_used"),
            tokens_used = result.get("tokens_used"),
        )

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    except Exception as e:
        print("\n" + "=" * 50)
        print("🚨 ERROR DI /chat")
        traceback.print_exc()
        print("=" * 50 + "\n")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================
# POST /api/v1/preprocess
# Kalkulasi otomatis dari raw input user
# Dipanggil setelah user submit form settings + transaksi
# ============================================================

@router.post(
    "/preprocess",
    response_model=PreprocessResponse,
    summary="Preprocessing data transaksi",
    description="""
    Terima data mentah dari form user (business settings + transaksi harian),
    hitung semua metrik otomatis (profit, HPP, BEP, cashflow status, dll).
    
    Response berisi MLPredictionContext yang siap dikirim ke /chat.
    Frontend cukup simpan response ini di state, lalu attach ke setiap request /chat.
    """
)
async def preprocess(request: PreprocessRequest):
    try:
        result = preprocess_transactions(request)
        return result

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        print("\n" + "=" * 50)
        print("🚨 ERROR DI /preprocess")
        traceback.print_exc()
        print("=" * 50 + "\n")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================
# GET /api/v1/health
# Health check — untuk Docker healthcheck dan monitoring
# ============================================================

@router.get(
    "/health",
    summary="Health check",
    tags=["System"]
)
async def health():
    import os
    api_key_set = bool(os.getenv("OPENROUTER_API_KEY"))
    return {
        "status":      "healthy",
        "api_key_set": api_key_set,
        "message":     "Coffee Advisor API is running 🚀"
    }
