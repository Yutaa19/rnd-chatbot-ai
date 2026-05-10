# ============================================================
# Dockerfile — Coffee Advisor API
# Base: Python 3.11 slim (ringan, ~50MB vs full ~900MB)
# ============================================================

FROM python:3.11-slim

# Metadata
LABEL maintainer="Coffee Advisor Team"
LABEL description="Coffee Shop Financial Advisor API"

# Set working directory
WORKDIR /app

# ============================================================
# Install dependencies dulu (sebelum copy code)
# Docker layer caching: kalau requirements.txt tidak berubah,
# layer ini tidak perlu rebuild → docker build lebih cepat
# ============================================================

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================
# Copy source code
# ============================================================

COPY app/ ./app/

# ============================================================
# Environment defaults (bisa di-override via docker-compose)
# ============================================================

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Port yang di-expose (harus sama dengan uvicorn --port)
EXPOSE 8000

# ============================================================
# Health check — Docker akan restart container jika unhealthy
# ============================================================

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/v1/health').raise_for_status()" \
    || exit 1

# ============================================================
# Run command
# --host 0.0.0.0 wajib di Docker agar bisa diakses dari luar container
# ============================================================

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
