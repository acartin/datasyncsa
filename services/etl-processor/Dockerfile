FROM python:3.12-slim

# Install System Dependencies (GDAL, Tesseract, Postgres, Redis)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libwebp-dev zlib1g-dev libjpeg-dev \
    postgresql-client git nano openssh-client poppler-utils \
    tesseract-ocr libgeos-dev libgdal-dev gdal-bin redis-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python Dependencies (Geo + Data + OCR)
# Note: Using --break-system-packages is not needed in venv or container usually, 
# but consistent with user script style. In Docker proper practice is just pip install.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create ETL Structure
RUN mkdir -p /app/src \
    /app/staging/images_raw /app/staging/documents_in /app/staging/data_raw /app/staging/temp_work \
    /app/storage/images_web /app/storage/documents_arch /app/storage/datasets_clean

COPY . .

# Default Command (API Mode)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

