from pydantic import BaseModel, Field, field_validator
from typing import Optional
import datetime


class BusinessSettings(BaseModel):
    fixed_cost_monthly: int = Field(
        ...,
        description="Total biaya tetap bulanan dalam Rupiah (gaji, sewa, wifi, dll)"
    )
    variable_cost_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Persentase HPP/variable cost dari omset (0-100)"
    )

    @field_validator("fixed_cost_monthly")
    @classmethod
    def validate_fixed_cost(cls, v):
        if v < 0:
            raise ValueError("Fixed cost tidak boleh negatif")
        return v


class DailyTransaction(BaseModel):
    """
    Data transaksi harian — input minimal dari user.
    'tanggal' dipakai sebagai nama field biar tidak clash dengan built-in date.
    Frontend tetap kirim JSON key 'date' karena ada alias.
    """
    tanggal: datetime.date = Field(
        ...,
        description="Tanggal transaksi format YYYY-MM-DD",
        alias="date"
    )
    total_sales: int = Field(..., ge=0, description="Total omset kotor hari itu (Rupiah)")
    transaction_count: Optional[int] = Field(default=None, ge=0, description="Jumlah struk/pelanggan (opsional)")

    model_config = {"populate_by_name": True}


class MLPredictionContext(BaseModel):
    avg_daily_sales: float = Field(default=0.0, description="Rata-rata omset harian (7 hari terakhir)")
    avg_daily_profit: float = Field(default=0.0, description="Rata-rata profit bersih harian")
    avg_ticket_size: Optional[float] = Field(default=None, description="Rata-rata nilai per transaksi")
    current_hpp_percentage: float = Field(default=0.0, description="HPP aktual dalam persentase omset")
    daily_fixed_cost: float = Field(default=0.0, description="Fixed cost harian (monthly/30)")
    cash_runway_days: Optional[int] = Field(default=None, description="Estimasi berapa hari kas bertahan")
    forecast_trend: str = Field(default="STABIL", description="Tren: NAIK / TURUN / STABIL")
    forecast_percentage: float = Field(default=0.0, description="Persentase perubahan prediksi")
    forecast_period_days: int = Field(default=30, description="Periode prediksi dalam hari")
    cashflow_status: str = Field(default="NORMAL", description="DEFISIT / IMPAS / SURPLUS_TIPIS / SURPLUS_AMAN")
    warning: Optional[str] = Field(default=None, description="Warning dari sistem jika kondisi kritis")
    recommendation: Optional[str] = Field(default=None, description="Rekomendasi otomatis dari sistem")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="Pertanyaan dari user")
    context: MLPredictionContext = Field(default_factory=MLPredictionContext)


class ChatResponse(BaseModel):
    reply: str
    status: str = "success"
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None


class PreprocessRequest(BaseModel):
    settings: BusinessSettings
    transactions: list[DailyTransaction] = Field(..., min_length=1)


class PreprocessResponse(BaseModel):
    context: MLPredictionContext
    summary: dict
