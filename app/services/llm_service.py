import os
import httpx
from app.models.schemas import MLPredictionContext

# KONFIGURASI OPENROUTER

OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
YOUR_SITE_URL       = os.getenv("YOUR_SITE_URL", "http://localhost:8000")
YOUR_APP_NAME       = os.getenv("YOUR_APP_NAME", "Coffee Advisor AI")

# Model gratis yang bagus untuk Bahasa Indonesia
# Prioritas: DeepSeek (paling kuat) → Llama 3.3 → Mistral
OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "qwen/qwen3-next-80b-a3b-instruct:free"  # gratis, sangat bagus BahasaIndo
)

# Fallback models kalau model utama tidak tersedia
FALLBACK_MODELS = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "baidu/cobuddy:free",
    "poolside/laguna-m.1:free",
]

MAX_TOKENS = 600

# SYSTEM PROMPT BUILDER
# Inject konteks ML prediction ke dalam prompt

SYSTEM_PROMPT_BASE = """Kamu adalah advisor keuangan coffee shop Gen Z. Gunakan bahasa gaul (lo/gue), suportif tapi tegas soal uang.
HANYA gunakan angka dari [DATA SISTEM] dalam jawaban. DILARANG mengarang angka yang tidak ada di [DATA SISTEM].

Format jawaban WAJIB:
[Insight] analisis kondisi bisnis berdasarkan data
[Metric] perhitungan eksplisit dari angka di DATA SISTEM
[Action] 1-2 langkah konkret yang bisa dilakukan hari ini
[Disclaimer] catatan singkat bahwa ini proyeksi algoritma"""


def build_system_prompt() -> str:
    """System prompt selalu konsisten — konteks ada di user message"""
    return SYSTEM_PROMPT_BASE


def build_user_message(user_query: str, context: MLPredictionContext) -> str:
    """
    Inject konteks ML prediction ke dalam user message.
    Format ini SAMA dengan yang ada di dataset training.
    """
    # Format angka rupiah
    def rupiah(val):
        return f"Rp{int(val):,}".replace(",", ".")

    # Build data context section
    ctx_lines = [
        f"• Rata-rata Omset Harian: {rupiah(context.avg_daily_sales)}/hari",
        f"• Rata-rata Profit Harian: {rupiah(context.avg_daily_profit)}/hari",
        f"• HPP Saat Ini: {context.current_hpp_percentage:.1f}% dari omset",
        f"• Fixed Cost Harian: {rupiah(context.daily_fixed_cost)}/hari",
        f"• Forecast Cashflow {context.forecast_period_days} Hari: "
        f"{context.forecast_trend} {abs(context.forecast_percentage):.1f}%",
        f"• Status Cashflow: {context.cashflow_status}",
    ]

    # Field opsional — hanya tampil kalau ada nilainya
    if context.avg_ticket_size:
        ctx_lines.insert(
            2,
            f"• Avg Ticket Size: {rupiah(context.avg_ticket_size)}/transaksi"
        )

    if context.cash_runway_days is not None:
        icon = "⚠️ KRITIS" if context.cash_runway_days < 14 else "✅"
        ctx_lines.append(
            f"• Cash Runway: {context.cash_runway_days} hari {icon}"
        )

    if context.warning:
        ctx_lines.append(f"• ⚠️ Warning: {context.warning}")

    if context.recommendation:
        ctx_lines.append(f"• 💡 Rekomendasi Sistem: {context.recommendation}")

    context_block = "\n".join(ctx_lines)

    return f"[DATA SISTEM]\n{context_block}\n\n[PERTANYAAN USER]\n{user_query}"


# ============================================================
# OPENROUTER API CALL
# ============================================================

async def call_openrouter(
    messages: list[dict],
    model: str = OPENROUTER_MODEL,
    timeout: float = 30.0
) -> dict:
    """
    Call OpenRouter API secara async.
    Return dict berisi reply, model_used, tokens_used.
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY belum diset! "
            "Tambahkan ke file .env: OPENROUTER_API_KEY=sk-or-..."
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": YOUR_SITE_URL,   # wajib untuk OpenRouter
        "X-Title": YOUR_APP_NAME,         # nama app di OpenRouter dashboard
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
        response = await client.post(
            OPENROUTER_BASE_URL,
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()

    reply       = data["choices"][0]["message"]["content"].strip()
    model_used  = data.get("model", model)
    tokens_used = data.get("usage", {}).get("total_tokens")

    return {
        "reply": reply,
        "model_used": model_used,
        "tokens_used": tokens_used,
    }


async def generate_response(
    message: str,
    context: MLPredictionContext
) -> dict:
    """
    Main function — dipanggil dari route handler.
    Coba model utama, fallback ke model lain jika gagal.
    Return dict: reply, model_used, tokens_used
    """
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user",   "content": build_user_message(message, context)},
    ]

    # Coba model utama dulu
    models_to_try = [OPENROUTER_MODEL] + FALLBACK_MODELS

    last_error = None
    for model in models_to_try:
        try:
            result = await call_openrouter(messages, model=model)
            return result
        except httpx.HTTPStatusError as e:
            # 429 = rate limit, 503 = model tidak tersedia → coba fallback
            if e.response.status_code in (429, 503):
                last_error = e
                continue
            raise  # error lain langsung raise
        except Exception as e:
            last_error = e
            continue

    # Semua model gagal
    raise RuntimeError(
        f"Semua model OpenRouter tidak tersedia saat ini. "
        f"Error terakhir: {last_error}"
    )
