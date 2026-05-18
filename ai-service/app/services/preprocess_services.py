from app.models.shcema import (
    MLPredictionContext,
    PreprocessRequest,
    PreprocessResponse,
)
from datetime import date
from statistics import mean

# prepricessing service untuk menyiapkan data sebelum masuk ke model ML

def preprocess_transactions(req: PreprocessRequest) -> PreprocessResponse:
    """
    Kalkulasi yang di lakukan:
    1. Daily fixed cost = monthly fixed cost / 30
    2. Variable (hpp) = total_sales * variable_cost_percentage / 100
    3. Daily profit = total_sales - variable_cost - daily_fixed_cost
    4. Rata rata omset harian 7 hari terakhir
    5. avg_ticket_size = total_sales / transaction_count (jika transaction_count > 0)
    6. cashflow_status = Defisit / Impas / Surplus tipis / Surplus sehat
    7. Warning jika kondisi kritis
    """
    settings = req.settings
    transactions = req.transactions

    # sort by date
    transactions = sorted(transactions, key=lambda x: x.tanggal)

    # hitung daily fixed cost
    daily_fixed_cost = settings.fixed_cost_monthly / 30

    # kalkulasi per hari
    processed_days = []
    for tx in transactions:
        variable_cost = tx.total_sales * (settings.variable_cost_percentage / 100)
        daily_profit = tx.total_sales - variable_cost - daily_fixed_cost
        avg_ticket = (
            tx.total_sales / tx.transaction_count
            if tx.transaction_count and tx.transaction_count > 0
            else None
        )
        processed_days.append({
            "tanggal": tx.tanggal,
            "total_sales": tx.total_sales,
            "variable_cost": variable_cost,
            "daily_profit": daily_profit,
            "transaction_count": tx.transaction_count,
            "avg_ticket_size": avg_ticket
        })

    # ambil 7 hari terakhir untuk kalkulasi rata-rata

    last_7_days = processed_days[-7:] if len(processed_days) >= 7 else processed_days

    avg_daily_sales = mean(d["total_sales"] for d in last_7_days)
    avg_daily_profit = mean(d["daily_profit"] for d in last_7_days)

        # avg ticket hanya ada jika ada transaction count > 0
    ticket_data = [d["avg_ticket_size"] for d in last_7_days if d["avg_ticket_size"] is not None]
    avg_ticket_size = mean(ticket_data) if ticket_data else None

        # hpp aktual dalam persentase omset
    current_hpp_percentage = settings.variable_cost_percentage

        # forecast oleh model Ml (dummy logic untuk contoh)
    forecast_trend = "STABIL"
    forecast_percentage = 0.0

    if len(last_7_days) >= 6:
        first_half = mean(d["total_sales"] for d in last_7_days[:3])
        last_half = mean(d["total_sales"] for d in last_7_days[-3:])

        if first_half > 0:
            change_pct = ((last_half - first_half) / first_half) * 100
            forecast_percentage = round(abs(change_pct), 1)
            if change_pct > 3:
                forecast_trend = "NAIK"
            elif change_pct < -3:
                 forecast_trend = "TURUN"
            else:
                 forecast_trend = "STABIL"
                
        # cashflow status
    total_profit_last_7 = sum(d["daily_profit"] for d in last_7_days)
    avg_profit_per_day = total_profit_last_7 / len(last_7_days) if last_7_days else 0

    if avg_profit_per_day > 100.000:
         cashflow_status = "Surplus sehat"
    elif avg_profit_per_day > 0:
         cashflow_status = "Surplus tipis"
    elif avg_profit_per_day == 0:
         cashflow_status = "Impas"
    else:
         cashflow_status = "Defisit"

        # cash runway estimation

    cash_runway_days = None
    if avg_profit_per_day < 0:
           # berapa hai sampai bangkrut kalau trend ini terus berlanjut
        possitive_profits = [d["daily_profit"] for d in processed_days if d["daily_profit"] > 0]
        if possitive_profits:
            estimated_cash_buffer = sum(possitive_profits[-30:])
            daily_burn = abs(avg_profit_per_day)
            cash_runway_days = int(estimated_cash_buffer / daily_burn) if daily_burn > 0 else None

            # warning dan recommendation
    warning = None
    recommendation = None

    if cashflow_status == "Defisit":
            warning = f"Bisnis dalam kondisi Defisit {abs(avg_profit_per_day):,.0f} Rp/hari per hari. Estimasi kas bertahan {cash_runway_days} Rp/hari"
            recommendation = "Audit pengeluaran segera dan naikan omset minimum BEP"
    elif current_hpp_percentage > 50:
             warning = f"HPP saai ini {current_hpp_percentage:.1f}% terlalu tinggi - batas aman ≤40%"
             recommendation = "Review resep dan negosiasi harga supplier untuk turunkan HPP"

    elif forecast_trend =="TURUN" and forecast_percentage > 10:
             warning = f"Tren penjualan diprediksi turun {forecast_percentage:.1f}% dalam 7 hari ke depan"
             recommendation = "Lakukan promosi dan tingkatkan layanan untuk stabilkan penjualan"
            
    if cash_runway_days is not None and cash_runway_days < 14:
            warning = f"⚠️ KRITIS: Cash runway estimasi hanya {cash_runway_days} hari"
            recommendation = "Prioritas: tambah pemasukan atau kurangi biaya tetap segera"
            
        # membangun MLPredictionContext untuk response
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
