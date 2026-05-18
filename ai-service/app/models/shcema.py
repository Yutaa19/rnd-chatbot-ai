from pydantic import BaseModel, Field, field_validator
from typing import Optional
import datetime

class BusinessSettings(BaseModel):
    fixed_cost_monthly: int = Field(
        ...,
        description="Total biaya tetap bulanan dalam bulanan dalam rupiah (gaji, sewa, wifi, dll)"
    )
    variable_cost_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Persentase HPP/varibale cost dari omset (0-100)"
    )
    @field_validator("fixed_cost_monthly")
    @classmethod
    def validate_fixed_cost(cls, v):
        if v < 0:
            raise ValueError("Fixed cost tidak boleh negatif")
        return v

class DailyTransaction(BaseModel):
    """
        Data Transaksi harian - input minimal dari user /
        'tanggal' di pakai sebagai nama field biar tidak clash dengan built-in date.
        frondend tetap kirim json key 'date' karena ada alias. 
    """
    tanggal: datetime.date = Field(
        ...,
        description="Tanggal transaksi harian (format: YYYY-MM-DD)",
        alias="date"
    )
    total_sales: int = Field(
        ...,
        ge=0,
        description="Total penjualan harian dalam rupiah"
    )
    transaction_count : Optional[int] = Field(default=None, ge=0, description="Jumlah sturk/pelanggan (opsional)")
    model_config = {
        "populate_by_name" : True
    }

class MLPredictionContext(BaseModel):
    avg_daily_sales: float = Field(default=0.0, description="Rata-rata omset harian 7 hari terakhir")
    avg_daily_profit: float = Field(default=0.0, description="Rata-rata profit bersih harian")
    avg_ticket_size: float = Field(default=0.0, description="Rata-rata nilai per transaksi")
    current_hpp_percentage: float =Field(default=0.0, description="HPP aktual dalam persentase omset")
    daily_fixed_cost: float = Field(default=0.0, description="Fixed cost harian (monthly/30)")
    cash_runway_days: Optional[int] = Field(default=None, description="Estimasi berapa hari kas bertahan")
    forecast_trend: str = Field(default="stabil", description="Tren: NAIK / TURUN / STABIL")
    forecast_percentage: float = Field(default=0.0, description="Persentase perubahan prediksi")
    forecast_period_days: int = Field(default=7, description="Periode preidksi dalam hari")
    cashflow_status: str = Field(default="Normal", description="Defisit / Impas / Surplus_tipis / Surplus_sehat")
    warning: Optional[str] = Field(default=None, description="Warning dari sitem jika kondisi kritis")
    recommendation: Optional[str] = Field(default=None, description="Rekomendasi otomatis dari sistem")

class ChatRequest(BaseModel):
    message: str = Field(..., description="Pesan input dari user untuk chatbot")
    context: MLPredictionContext = Field(default_factory=MLPredictionContext)

class ChatResponse(BaseModel):
    reply: str
    status: str = Field(default="success", description="Status response: success / error")
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None

class PreprocessRequest(BaseModel):
    settings: BusinessSettings
    transactions: list[DailyTransaction] = Field(..., min_length=1)

class PreprocessResponse(BaseModel):
    context: MLPredictionContext
    summary: dict