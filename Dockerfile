# One image: builds the React app, then serves it and the API from a single uvicorn process.

# ---- frontend build ----
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- runtime ----
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    CHROMA_PERSIST_DIR=/data/chroma PORT=8000
WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Bake ChromaDB's default embedding model into the image so the first request doesn't download it.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as E; E()(['warm up'])"

COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY --from=frontend /frontend/dist frontend/dist

RUN mkdir -p /data/chroma
EXPOSE 8000
# Apply migrations, then serve. $PORT is set by Render/Railway/Fly.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.serve:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
