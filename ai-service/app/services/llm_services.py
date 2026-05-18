import os
import httpx
from app.models.shcema import MLPredictionContext 

# konfigurasi openrouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen3-next-80b-a3b-instruct:free")
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")
APP_NAME = "CoffeeShopBot"

MAX_TOKENS = 600

# system prompt untuk chatbot
SYSTEM_PROMPT = """Kamu adalah advisor keuangan coffee shop Gen Z. Gunakan gaul (lo/gue), suportif tapi tegas soal uang.
HANYA gunakan angka dari [DATA SISTEM] dalam jawaban. DILARANG mengarang angka yang tidak ada di [DATA SISTEM].

Format jawaban WAJIB:
[Insight] analisis kondisi bisnis berdasarkan data
[Metric] perhitungan eksplisit dari angka di DATA SISTEM
[Action] 1-2 langkah konkret yang bisa dilakukan hari ini
[Disclaimer] catatan singkat bahwa ini proyeksi algoritma"""

def build_system_prompt() -> str:
    return SYSTEM_PROMPT

def build_user_message(user_query: str, context: MLPredictionContext) -> str:
    def format_rupiah(val):
        return f"Rp{val:,.0f}".replace(",", ".")
    
    ctx_lines = [
        f"Rata-rata omset harian 7 hari terakhir: {format_rupiah(context.avg_daily_sales)}",
        f"Rata-rata profit bersih harian: {format_rupiah(context.avg_daily_profit)}",
        f"HPP aktual dalam persentase omset: {context.current_hpp_percentage:.2f}%",
        f"Fixed cost harian: {format_rupiah(context.daily_fixed_cost)}",
        f"Tren: {context.forecast_trend} ({context.forecast_percentage:.2f}% dalam {context.forecast_period_days} hari ke depan)",
        f"Cashflow status: {context.cashflow_status}",
    ]

    
    if context.avg_ticket_size is not None:
        ctx_lines.insert(2, f"Rata-rata nilai per transaksi: {format_rupiah(context.avg_ticket_size)}")

    if context.cash_runway_days is not None:
        icon = "⚠️ Kritis" if context.cash_runway_days <= 7 else "✅"
        # PERBAIKAN: Variabel icon dimasukkan ke string
        ctx_lines.append(f"Estimasi berapa hari kas bertahan: {context.cash_runway_days} hari {icon}")
        
    if context.warning:
        ctx_lines.append(f"Warning dari sistem: {context.warning}")
    else:
        ctx_lines.append("Warning dari sistem: Tidak ada")
        
    if context.recommendation:
        ctx_lines.append(f"Rekomendasi sistem: {context.recommendation}")
    
    context_block = "\n".join(ctx_lines)
    return f"[DATA SISTEM]\n{context_block}\n\n[PERTANYAAN USER]\n{user_query}"

async def call_openrouter(messages: list[dict], model: str = OPENROUTER_MODEL, timeout: float = 30.0) -> dict:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY tidak ditemukan. Pastikan sudah di set di environment variables.")
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": SITE_URL,  
        "X-Title": APP_NAME,         
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7,
        "top_p": 0.9,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        raw_content = data["choices"][0]["message"].get("content")
        if raw_content is not None:
            reply = raw_content.strip()
        else:
            reply = "Maaf, model AI tidak dapat memberikan respons saat ini (mengembalikan nilai kosong)."
        model_used = data.get("model", model)
        # PERBAIKAN: Hilangkan koma berlebih (,)
        tokens_used = data.get("usage", {}).get("total_tokens")

        return {
            "reply": reply,
            "model_used": model_used,
            "tokens_used": tokens_used
        }

async def generate_response(message: str, context: MLPredictionContext) -> dict:
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": build_user_message(message, context)}
    ]

    # Tambahkan fallback model agar retry logic berguna
    FALLBACK_MODELS = ["nvidia/nemotron-3-super-120b-a12b:free", "inclusionai/ring-2.6-1t:free", "poolside/laguna-m.1:free"] 
    models_to_try = [OPENROUTER_MODEL] + FALLBACK_MODELS

    last_error = None
    for model in models_to_try:
        try:
            result = await call_openrouter(messages, model=model)
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 503):
                last_error = e
                continue 
            # selain 429/503 (misal salah API Key / 401), langsung lemparkan error
            raise RuntimeError(f"OpenRouter API Error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            last_error = e
            continue

    # Exception 
    raise RuntimeError(
        f"Semua model gagal dipanggil setelah {len(models_to_try)} percobaan. Terakhir error: {last_error}"
    )