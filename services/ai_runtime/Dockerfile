FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY services/ai_runtime/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY services /app/services
COPY schemas /app/schemas

WORKDIR /app/services/ai_runtime

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
