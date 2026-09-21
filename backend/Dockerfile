# build
FROM python:3.11-slim AS builder

WORKDIR /app

# bagimliliklar
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# runtime
FROM python:3.11-slim

WORKDIR /app

# pip kütüphaneleri
COPY --from=builder /root/.local /root/.local

COPY . .

# path'e pip --user dizinini ekle
ENV PATH=/root/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]