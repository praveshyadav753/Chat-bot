# # ── Builder stage ─────────────────────────────────────────────────────────────
# FROM python:3.12-slim AS builder

# COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# WORKDIR /app

# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     libpq-dev \
#     libmagic1 \
#     libmagic-dev \
#     poppler-utils \
#     tesseract-ocr \
#     libreoffice \
#     pandoc \
#     && rm -rf /var/lib/apt/lists/*

# COPY pyproject.toml uv.lock ./
# RUN uv sync --frozen --no-dev

# # ── Runtime stage ─────────────────────────────────────────────────────────────
# FROM python:3.12-slim AS runtime

# COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# WORKDIR /app

# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \      
#     libpq-dev \            
#     libpq5 \
#     libmagic1 \
#     libmagic-dev \         
#     poppler-utils \
#     tesseract-ocr \
#     libreoffice \
#     pandoc \
#     curl \
#     && rm -rf /var/lib/apt/lists/*

# # Copy only pyproject and lock file first
# COPY pyproject.toml uv.lock ./

# # Install directly in runtime ✅
# RUN uv sync --frozen --no-dev

# # Copy source code AFTER install (better layer caching)
# COPY . .

# RUN mkdir -p uploads chroma_db logs

# ENV PATH="/app/.venv/bin:$PATH"
# ENV VIRTUAL_ENV="/app/.venv"

# EXPOSE 8000

# HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
#     CMD curl -f http://localhost:8000/ || exit 1

# CMD ["uvicorn", "app.main:app", \
#      "--host", "0.0.0.0", \
#      "--port", "8000", \
#      "--workers", "1", \
#      "--log-level", "info"]

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    libmagic-dev \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    libreoffice \
    pandoc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install deps first (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Force headless opencv — replaces GUI version pulled by unstructured
RUN .venv/bin/pip install opencv-python-headless

# Copy source code
COPY . .

RUN mkdir -p chroma_db logs

ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info"]