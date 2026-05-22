from app.models.shcema import (
    MLPredictionContext,
    PreprocessRequest,
    PreprocessResponse,
)
from statistics import mean

# ── Import inference service ───────────────────────────────────────────────────
# predict_cashflow() return None jika model belum di-load (fallback aman)
from app.services.inference_service import predict_cashflow, is_model_ready, WINDOW_SIZE


def preprocess_transactions(req: PreprocessRequest) -> PreprocessResponse:
    """
    Kalkulasi yang dilakukan:
    1.  Daily fixed cost = monthly fixed cost / 30
    2.  Variable (hpp)  = total_sales * variable_cost_percentage / 100
    3.  Daily profit    = total_sales - variable_cost - daily_fixed_cost
    4.  Rata-rata omset harian 7 hari terakhir
    5.  avg_ticket_size = total_sales / transaction_count (jika ada)
    6.  cashflow_status = Defisit / Impas / Surplus tipis / Surplus sehat
    7.  Forecast trend & percentage dari LSTM (fallback heuristik jika < 14 hari)
    8.  Warning & recommendation otomatis
    """
    settings     = req.settings
    transactions = req.transactions

    # Sort kronologis
    transactions = sorted(transactions, key=lambda x: x.tanggal)

    daily_fixed_cost = settings.fixed_cost_monthly / 30

    # ── Kalkulasi per hari ────────────────────────────────────────────────────
    processed_days = []
    for tx in transactions:
        variable_cost = tx.total_sales * (settings.variable_cost_percentage / 100)
        daily_profit  = tx.total_sales - variable_cost - daily_fixed_cost
        avg_ticket    = (
            tx.total_sales / tx.transaction_count
            if tx.transaction_count and tx.transaction_count > 0
            else None
        )
        processed_days.append({
            "tanggal":          tx.tanggal,
            "total_sales":      tx.total_sales,
            "variable_cost":    variable_cost,
            "daily_profit":     daily_profit,
            "transaction_count": tx.transaction_count,
            "avg_ticket_size":  avg_ticket,
        })

    # ── Inisialisasi semua variabel ───────────────────────────────────────────
    avg_daily_sales     = 0.0
    avg_daily_profit    = 0.0
    avg_ticket_size     = None
    avg_profit_per_day  = 0.0
    cash_runway_days    = None
    forecast_trend      = "STABIL"
    forecast_percentage = 0.0
    lstm_result         = None
    warning             = None
    recommendation      = None

    # ── Rata-rata 7 hari terakhir ─────────────────────────────────────────────
    last_7_days = processed_days[-7:] if len(processed_days) >= 7 else processed_days

    if last_7_days:
        avg_daily_sales    = mean(d["total_sales"]  for d in last_7_days)
        avg_daily_profit   = mean(d["daily_profit"] for d in last_7_days)
        avg_profit_per_day = avg_daily_profit

        ticket_data     = [d["avg_ticket_size"] for d in last_7_days if d["avg_ticket_size"] is not None]
        avg_ticket_size = mean(ticket_data) if ticket_data else None

    current_hpp_percentage = settings.variable_cost_percentage

    # ── Forecast: LSTM jika data cukup, heuristik jika tidak ─────────────────
    historical_sales = [d["total_sales"] for d in processed_days]

    forecast_trend      = "STABIL"
    forecast_percentage = 0.0

    lstm_result         = None  # ← inisialisasi dulu

    if is_model_ready() and len(historical_sales) >= WINDOW_SIZE:
        try:
            lstm_result         = predict_cashflow(historical_sales)
            forecast_trend      = lstm_result["forecast_trend"]
            forecast_percentage = lstm_result["forecast_percentage"]
            print(f"✅ LSTM forecast: {forecast_trend} ({forecast_percentage}%)")
        except Exception as e:
            print(f"⚠️  LSTM inference error: {e}. Fallback ke heuristik.")
            forecast_trend, forecast_percentage = _heuristic_forecast(last_7_days)
    else:
        forecast_trend, forecast_percentage = _heuristic_forecast(last_7_days)
        # ── Cashflow status ───────────────────────────────────────────────────────
        avg_profit_per_day = mean(d["daily_profit"] for d in last_7_days)

    if avg_profit_per_day > 100_000:
        cashflow_status = "Surplus sehat"
    elif avg_profit_per_day > 0:
        cashflow_status = "Surplus tipis"
    elif avg_profit_per_day == 0:
        cashflow_status = "Impas"
    else:
        cashflow_status = "Defisit"

    # ── Cash runway ───────────────────────────────────────────────────────────
    cash_runway_days = None
    if avg_profit_per_day < 0:
        positive_profits = [d["daily_profit"] for d in processed_days
                            if d["daily_profit"] > 0]
        if positive_profits:
            estimated_cash_buffer = sum(positive_profits[-30:])
            daily_burn            = abs(avg_profit_per_day)
            cash_runway_days      = int(estimated_cash_buffer / daily_burn) if daily_burn > 0 else 0
        else:
            # semua hari negatif — kas dianggap sudah kritis
            cash_runway_days = 0
        # ── Warning & recommendation ──────────────────────────────────────────────
    warning        = None
    recommendation = None

    if cashflow_status == "Defisit":
        if cash_runway_days is not None and cash_runway_days > 0:
            warning = (
                f"Bisnis dalam kondisi Defisit Rp{abs(avg_profit_per_day):,.0f}/hari. "
                f"Estimasi kas bertahan {cash_runway_days} hari."
            )
        else:
            warning = (
                f"Bisnis dalam kondisi Defisit Rp{abs(avg_profit_per_day):,.0f}/hari. "
                f"Kas sudah dalam kondisi kritis."
            )
        recommendation = "Audit pengeluaran segera dan naikkan omset minimum BEP."
            
    elif current_hpp_percentage > 50:
        warning        = f"HPP saat ini {current_hpp_percentage:.1f}% terlalu tinggi — batas aman ≤40%."
        recommendation = "Review resep dan negosiasi harga supplier untuk turunkan HPP."

    elif forecast_trend == "TURUN" and forecast_percentage > 10:
        warning        = f"Tren penjualan diprediksi turun {forecast_percentage:.1f}% dalam 7 hari ke depan."
        recommendation = "Lakukan promosi dan tingkatkan layanan untuk stabilkan penjualan."

    # Override jika cash runway kritis (prioritas tertinggi)
    if cash_runway_days is not None and cash_runway_days < 14:
        warning        = f"⚠️ KRITIS: Cash runway estimasi hanya {cash_runway_days} hari."
        recommendation = "Prioritas: tambah pemasukan atau kurangi biaya tetap segera."

    # ── Bangun MLPredictionContext ─────────────────────────────────────────────
    context = MLPredictionContext(
        avg_daily_sales        = round(avg_daily_sales, 0),
        avg_daily_profit       = round(avg_daily_profit, 0),
        avg_ticket_size        = round(avg_ticket_size, 0) if avg_ticket_size else None,
        current_hpp_percentage = current_hpp_percentage,
        daily_fixed_cost       = round(daily_fixed_cost, 0),
        cash_runway_days       = cash_runway_days,
        forecast_trend         = forecast_trend,
        forecast_percentage    = forecast_percentage,
        forecast_period_days   = 7,
        cashflow_status        = cashflow_status,
        warning                = warning,
        recommendation         = recommendation,
        predictions            = lstm_result["predictions"] if lstm_result else None,  
)

    # ── Summary untuk dashboard ───────────────────────────────────────────────
    summary = {
        "total_days_analyzed":   len(processed_days),
        "total_sales_all_time":  sum(d["total_sales"]  for d in processed_days),
        "total_profit_all_time": sum(d["daily_profit"] for d in processed_days),
        "best_day":  max(processed_days, key=lambda x: x["total_sales"], default=None),
        "worst_day": min(processed_days, key=lambda x: x["total_sales"], default=None),
        "bep_daily": round(daily_fixed_cost / (1 - settings.variable_cost_percentage / 100), 0),
        "lstm_active": is_model_ready() and len(historical_sales) >= WINDOW_SIZE,
    }

    if summary["best_day"]:
        summary["best_day"] = {
            "date":        str(summary["best_day"]["tanggal"]),
            "total_sales": summary["best_day"]["total_sales"],
        }
    if summary["worst_day"]:
        summary["worst_day"] = {
            "date":        str(summary["worst_day"]["tanggal"]),
            "total_sales": summary["worst_day"]["total_sales"],
        }

    return PreprocessResponse(context=context, summary=summary)


# ── Helper: fallback heuristik ────────────────────────────────────────────────

def _heuristic_forecast(last_7_days: list) -> tuple[str, float]:
    """
    Estimasi tren sederhana dari data 7 hari terakhir.
    Dipakai ketika data historis < 14 hari atau model belum tersedia.
    """
    if len(last_7_days) < 6:
        return "STABIL", 0.0

    first_half = mean(d["total_sales"] for d in last_7_days[:3])
    last_half  = mean(d["total_sales"] for d in last_7_days[-3:])

    if first_half == 0:
        return "STABIL", 0.0

    change_pct = ((last_half - first_half) / first_half) * 100

    if change_pct > 3:
        return "NAIK", round(abs(change_pct), 1)
    elif change_pct < -3:
        return "TURUN", round(abs(change_pct), 1)
    else:
        return "STABIL", round(abs(change_pct), 1)