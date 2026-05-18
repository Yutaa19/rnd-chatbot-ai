
FROM python:3.11-slim

# Metadata
LABEL maintainer="Coffee Advisor Team"
LABEL description="Coffee Shop Financial Advisor API"

# Set working directory
WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


COPY app/ ./app/


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Port yang di-expose (harus sama dengan uvicorn --port)
EXPOSE 8000


HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/v1/health').raise_for_status()" \
    || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
