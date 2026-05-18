import traceback
from fastapi import APIRouter, HTTPException
from app.models.shcema import (ChatRequest, ChatResponse,PreprocessRequest,PreprocessResponse)
from app.services.llm_services import generate_response
from app.services.preprocess_services import preprocess_transactions

router = APIRouter(prefix="/api/v1", tags=["Chatbot advisor"])

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat dengan chatbot advisor",
    description="Endpoint untuk mengirim pesan ke chatbot advisor dan menerima balasan."
)
async def chat(request: ChatRequest):
    try:
        response = await generate_response(
            message=request.message,
            context=request.context
        )
        return ChatResponse(
            reply=response["reply"],
            model_used=response.get("model_used"),
            tokens_used=response.get("tokens_used")
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    
    except Exception as e:
        print("\n" + "=" * 50)
        print("🚨 ERROR DI /chat")
        traceback.print_exc()
        print("=" * 50 + "\n")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post(
    "/preprocess",
    response_model=PreprocessResponse,
    summary="Preprocess data transaksi harian",
    description="Endpoint untuk memproses data transaksi harian dan menghasilkan konteks prediksi."
)
async def preprocess(request: PreprocessRequest):
    try:
        result = preprocess_transactions(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    except Exception as e:
        print("\n" + "=" * 50)
        print("🚨 ERROR DI /preprocess")
        traceback.print_exc()
        print("=" * 50 + "\n")
        raise HTTPException(status_code=500, detail="Internal server error")
    
@router.get("/health", summary="Health check endpoint", description="Endpoint untuk memeriksa kesehatan API")
async def health_check():
    return {"status": "ok", "message": "API is healthy and running."}