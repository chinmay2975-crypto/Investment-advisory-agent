# One image: builds the React app, then serves it and the API from a single uvicorn process.
# Works on Hugging Face Spaces (runs as uid 1000), Render and Fly.io.

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

# Hugging Face Spaces run the container as uid 1000, so everything the app writes must belong to it.
RUN useradd -m -u 1000 user && mkdir -p /data/chroma && chown -R user /data /app
USER user
ENV HOME=/home/user

# Bake ChromaDB's default embedding model into the image so the first request doesn't download it.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as E; E()(['warm up'])"

COPY --chown=user app/ app/
COPY --chown=user alembic/ alembic/
COPY --chown=user alembic.ini ./
COPY --chown=user --from=frontend /frontend/dist frontend/dist

EXPOSE 8000
# Apply migrations, then serve. $PORT is set by Render/Fly; Spaces use app_port 8000.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.serve:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
