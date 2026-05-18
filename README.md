# Caffeinance: Platform Visualisasi Data Terotomasi dan AI Chatbot Advisor untuk UMKM Coffee Shop
## Deskripsi Proyek
Platform fintech yang dirancang khusus untuk UMKM coffee shop guna mengatasi masalah "Financial Blindspot" melalui:
- Otomatisasi proses data dari spreadsheet Excel menjadi dashboard visual komprehensif
- Prediksi arus kas menggunakan model Time-Series Forecasting (14-30 hari ke depan)
- AI Chatbot Advisor yang memberikan peringatan dini dan saran mitigasi krisis likuiditas
## Tim Proyek
| Nama | NIM | Peran | Status |
|------|-----|-------|--------|
| Muhammad Fathir Ramada | CFCC367D6Y2269 | Full-Stack Web | Aktif |
| Mohamad Rafly Andreanto | CACC964D6Y2603 | AI Engineer | Aktif |
| Nashwa Faiza Shakila | CACC277D6X1733 | AI Engineer | Aktif |
| Bintang Gilangkasa Syailendra | CDCC902D6Y1685 | Data Scientist | Aktif |
| Muhammad Jalaluddin mahfuhdo | CDCC944D6Y1131 | Data Scientist | Aktif |
| Dias Putra Kurnia Sandi | CFCC218D6Y0646 | Full-Stack Web | Aktif |
## Teknologi yang Digunakan
- **Frontend**: React dengan Vite
- **Backend**: Node.js dengan Express.js (RESTful API)
- **AI/ML**: TensorFlow (Functional API atau Model Subclassing untuk model kustom)
- **Data Processing**: Python untuk pembersihan dan transformasi data
- **Lainnya**: FastAPI/Flask untuk serving model AI
## Fitur Utama
Berdasarkan cakupan proyek:
1. **Domain Data Scientist**
   - Otomatisasi pembacaan, pembersihan, dan formatting data Excel
   - Analisis pola transaksi (tren keramaian, deteksi anomali pengeluaran)
   - Pembentukan metrik bisnis dan visualisasi dashboard
2. **Domain AI Engineer**
   - Model Prediksi Arus Kas (Time-Series Forecasting)
   - AI Chatbot Advisor untuk saran mitigasi keuangan
3. **Domain Full-Stack Web**
   - Autentikasi Pengguna
   - Input Rencana Anggaran
   - Input Transaksi Harian
   - Smart Dashboard dengan indikator Traffic Light


# ☕ Coffee Advisor API

AI Financial Advisor untuk owner Coffee Shop Gen Z.
Powered by **OpenRouter API** (model gratis) + **FastAPI** + **Docker**.

---

## 🚀 Cara Jalankan (untuk semua OS)

### Prasyarat
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) sudah terinstall

### Langkah-langkah

```bash
# 1. Clone repo
git clone <repo-url>
cd coffee-advisor-api

# 2. Setup environment
cp .env.example .env

nano .env   

# 4. Jalankan!
docker compose up --build


```

### Stop server
```bash
docker compose down
```

### Rebuild setelah ada perubahan kode
```bash
docker compose up --build
```

---

## 📡 API Endpoints

### `GET /api/v1/health`
Health check — cek apakah server dan API key sudah terkonfigurasi.

```bash
curl http://localhost:8000/api/v1/health
```

---

### `POST /api/v1/preprocess`
**Step 1** — Submit data bisnis + transaksi harian.
Backend akan hitung semua metrik otomatis.

```bash
curl -X POST http://localhost:8000/api/v1/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "fixed_cost_monthly": 6000000,
      "variable_cost_percentage": 40.0
    },
    "transactions": [
      {"date": "2026-05-01", "total_sales": 1200000, "transaction_count": 42},
      {"date": "2026-05-02", "total_sales": 1800000, "transaction_count": 61},
      {"date": "2026-05-03", "total_sales": 950000,  "transaction_count": 33},
      {"date": "2026-05-04", "total_sales": 1500000, "transaction_count": 52},
      {"date": "2026-05-05", "total_sales": 2100000, "transaction_count": 74},
      {"date": "2026-05-06", "total_sales": 2300000, "transaction_count": 81},
      {"date": "2026-05-07", "total_sales": 1100000, "transaction_count": 38}
    ]
  }'
```

**Response:** `MLPredictionContext` — simpan ini di frontend state!

---

### `POST /api/v1/chat`
**Step 2** — Kirim pertanyaan user + context dari step 1.

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "HPP gue 40% tapi cashflow masih minus, kenapa ya?",
    "context": {
      "avg_daily_sales": 1564285,
      "avg_daily_profit": -371428,
      "avg_ticket_size": 54776,
      "current_hpp_percentage": 40.0,
      "daily_fixed_cost": 200000,
      "cash_runway_days": 8,
      "forecast_trend": "TURUN",
      "forecast_percentage": 12.5,
      "forecast_period_days": 30,
      "cashflow_status": "DEFISIT",
      "warning": "Cash runway estimasi hanya 8 hari",
      "recommendation": "Prioritas: tambah pemasukan atau kurangi biaya tetap segera"
    }
  }'
```

---

## 🔄 Alur Integrasi Frontend

```
User input form (settings + transaksi)
          │
          ▼
POST /api/v1/preprocess
          │
          ▼ simpan di state frontend
MLPredictionContext
          │
User ketik pertanyaan di chatbot
          │
          ▼
POST /api/v1/chat (message + context)
          │
          ▼
AI Advisor reply 💬
```

---

## 🤖 Model OpenRouter yang Dipakai

Default: `openai/gpt-oss-120b:free`

Ganti model di `.env`:
```env
OPENROUTER_MODEL=openai/gpt-oss-120b:free
```

Cek semua model gratis di: https://openrouter.ai/models?q=:free

---

## 📁 Struktur Project

```
coffee-advisor-api/
├── app/
│   ├── main.py                    # FastAPI app + middleware
│   ├── models/
│   │   └── schemas.py             # Pydantic schemas (kontrak API)
│   ├── routes/
│   │   └── chat.py                # Endpoint /chat dan /preprocess
│   └── services/
│       ├── llm_service.py         # OpenRouter API integration
│       └── preprocess_service.py  # Kalkulasi metrik otomatis
├── .env.example                   # Template env (copy → .env)
├── .gitignore
├── docker-compose.yml             # docker compose up
├── Dockerfile
├── requirements.txt
└── README.md
```

---


