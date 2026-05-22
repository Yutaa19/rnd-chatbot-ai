FROM python:3.11-slim

LABEL maintainer="Caffeinance Team"
LABEL description="Caffeinance Coffee Shop Financial Advisor API"

WORKDIR /app

# Install dependencies Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Salin kode aplikasi
COPY app/ ./app/

# Salin artifact ML ke dalam image
# Pastikan kedua file ini sudah ada di folder ai-service/ sebelum docker build
COPY caffeinance_lstm.keras   ./caffeinance_lstm.keras
COPY caffeinance_scaler.pkl   ./caffeinance_scaler.pkl

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/v1/health').raise_for_status()" \
    || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]