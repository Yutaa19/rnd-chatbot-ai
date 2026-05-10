from app.models.schemas import (
    BusinessSettings,
    DailyTransaction,
    MLPredictionContext,
    PreprocessRequest,
    PreprocessResponse,
)
from datetime import date
from statistics import mean

# ============================================================
# PREPROCESSING SERVICE
# Kalkulasi semua angka dari raw input user
# Frontend TIDAK perlu hitung apapun — semua di sini
# ============================================================

def preprocess_transactions(req: PreprocessRequest) -> PreprocessResponse:
    """
    Terima raw input user (settings + transaksi harian),
    hitung semua metrik yang dibutuhkan chatbot.

    Kalkulasi yang dilakukan:
    1. Daily fixed cost = monthly fixed cost / 30
    2. Variable cost (HPP) = total_sales * variable_cost_percentage / 100
    3. Daily profit = total_sales - variable_cost - daily_fixed_cost
    4. Rata-rata 7 hari terakhir
    5. Avg ticket size (jika transaction_count tersedia)
    6. Cashflow status berdasarkan profit trend
    7. Warning jika kondisi kritis
    """
    settings     = req.settings
    transactions = req.transactions

    # Sort by date ascending
    transactions = sorted(transactions, key=lambda x: x.tanggal)

    # --- 1. Daily Fixed Cost ---
    daily_fixed_cost = settings.fixed_cost_monthly / 30

    # --- 2. Kalkulasi per hari ---
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
            "avg_ticket":       avg_ticket,
        })

    # --- 3. Ambil 7 hari terakhir untuk rata-rata ---
    last_7 = processed_days[-7:] if len(processed_days) >= 7 else processed_days

    avg_daily_sales  = mean(d["total_sales"]   for d in last_7)
    avg_daily_profit = mean(d["daily_profit"]   for d in last_7)

    # Avg ticket — hanya kalau ada data transaction_count
    ticket_data = [d["avg_ticket"] for d in last_7 if d["avg_ticket"] is not None]
    avg_ticket_size = mean(ticket_data) if ticket_data else None

    # --- 4. HPP aktual ---
    # HPP = variable cost / total sales (sudah fix dari setting, tapi kita expose)
    current_hpp_percentage = settings.variable_cost_percentage

    # --- 5. Forecast sederhana: tren dari 7 hari terakhir ---
    # Bandingkan 3 hari pertama vs 3 hari terakhir dari window 7 hari
    forecast_trend      = "STABIL"
    forecast_percentage = 0.0

    if len(last_7) >= 6:
        first_half = mean(d["total_sales"] for d in last_7[:3])
        last_half  = mean(d["total_sales"] for d in last_7[-3:])

        if first_half > 0:
            change_pct = ((last_half - first_half) / first_half) * 100
            forecast_percentage = round(abs(change_pct), 1)

            if change_pct > 3:
                forecast_trend = "NAIK"
            elif change_pct < -3:
                forecast_trend = "TURUN"
            else:
                forecast_trend = "STABIL"

    # --- 6. Cashflow Status ---
    total_profit_last_7 = sum(d["daily_profit"] for d in last_7)
    avg_profit_per_day  = total_profit_last_7 / len(last_7) if last_7 else 0

    if avg_profit_per_day > 100_000:
        cashflow_status = "SURPLUS_AMAN"
    elif avg_profit_per_day > 0:
        cashflow_status = "SURPLUS_TIPIS"
    elif avg_profit_per_day == 0:
        cashflow_status = "IMPAS"
    else:
        cashflow_status = "DEFISIT"

    # --- 7. Cash Runway Estimation ---
    # Estimasi sederhana: (estimasi kas) / |daily burn|
    # Kita tidak punya data kas aktual dari user, jadi pakai proxy:
    # kas proxy = total 7 hari profit (bisa negatif)
    cash_runway_days = None
    if avg_profit_per_day < 0:
        # Berapa hari sampai "bangkrut" kalau tren ini terus
        # Asumsi buffer kas = 30 hari profit positif terakhir
        positive_profits = [d["daily_profit"] for d in processed_days if d["daily_profit"] > 0]
        if positive_profits:
            estimated_cash_buffer = sum(positive_profits[-30:])
            daily_burn = abs(avg_profit_per_day)
            cash_runway_days = int(estimated_cash_buffer / daily_burn) if daily_burn > 0 else None

    # --- 8. Warning & Recommendation ---
    warning        = None
    recommendation = None

    if cashflow_status == "DEFISIT":
        warning = f"Bisnis dalam kondisi DEFISIT {abs(avg_profit_per_day):,.0f} Rp/hari"
        recommendation = "Audit pengeluaran segera dan naikkan omset minimum BEP"

    elif current_hpp_percentage > 50:
        warning = f"HPP {current_hpp_percentage:.0f}% terlalu tinggi — batas aman ≤40%"
        recommendation = "Review resep dan negosiasi harga supplier"

    elif forecast_trend == "TURUN" and forecast_percentage > 10:
        warning = f"Tren omset TURUN {forecast_percentage:.1f}% dalam 7 hari terakhir"
        recommendation = "Aktivasi promo atau cari sumber pendapatan tambahan"

    if cash_runway_days is not None and cash_runway_days < 14:
        warning = f"⚠️ KRITIS: Cash runway estimasi hanya {cash_runway_days} hari"
        recommendation = "Prioritas: tambah pemasukan atau kurangi biaya tetap segera"

    # --- Build MLPredictionContext ---
    context = MLPredictionContext(
        avg_daily_sales        = round(avg_daily_sales, 0),
        avg_daily_profit       = round(avg_daily_profit, 0),
        avg_ticket_size        = round(avg_ticket_size, 0) if avg_ticket_size else None,
        current_hpp_percentage = current_hpp_percentage,
        daily_fixed_cost       = round(daily_fixed_cost, 0),
        cash_runway_days       = cash_runway_days,
        forecast_trend         = forecast_trend,
        forecast_percentage    = forecast_percentage,
        forecast_period_days   = 30,
        cashflow_status        = cashflow_status,
        warning                = warning,
        recommendation         = recommendation,
    )

    # --- Summary untuk ditampilkan di dashboard ---
    summary = {
        "total_days_analyzed":   len(processed_days),
        "total_sales_all_time":  sum(d["total_sales"]   for d in processed_days),
        "total_profit_all_time": sum(d["daily_profit"]  for d in processed_days),
        "best_day": max(processed_days, key=lambda x: x["total_sales"], default=None),
        "worst_day": min(processed_days, key=lambda x: x["total_sales"], default=None),
        "bep_daily":             round(daily_fixed_cost / (1 - settings.variable_cost_percentage / 100), 0),
    }

    # Bersihkan summary agar serializable
    if summary["best_day"]:
        summary["best_day"] = {
            "date": str(summary["best_day"]["tanggal"]),
            "total_sales": summary["best_day"]["total_sales"]
        }
    if summary["worst_day"]:
        summary["worst_day"] = {
            "date": str(summary["worst_day"]["tanggal"]),
            "total_sales": summary["worst_day"]["total_sales"]
        }

    return PreprocessResponse(context=context, summary=summary)
