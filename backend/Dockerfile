# Slim base image; multi-stage not needed yet at Sprint 0 scale (no
# compiled frontend/asset build step lives in this image). Revisit if
# image size becomes a problem once ML/RAG dependencies are added.
FROM python:3.12-slim

WORKDIR /app

# System deps needed to build psycopg2/asyncpg wheels on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
