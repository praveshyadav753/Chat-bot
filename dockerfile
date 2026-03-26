FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    # PostgreSQL
    libpq5 \
    # File type detection (unstructured)
    libmagic1 \
    # PDF processing (unstructured[pdf])
    poppler-utils \
    tesseract-ocr \
    # libxcb + X11 — fixes "libxcb.so.1: cannot open shared object file"
    libxcb1 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    # OpenCV / image processing (libgl1-mesa-glx renamed in Debian trixie)
    libgl1 \
    libglib2.0-0 \
    # Office docs (unstructured[all-docs])
    libreoffice \
    pandoc \
    # Misc build/runtime
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install deps first (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source code
COPY . .

RUN mkdir -p uploads chroma_db logs

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