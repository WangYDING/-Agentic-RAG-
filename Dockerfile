FROM python:3.12-slim

ARG UV_VERSION=0.13.6
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    RAG_PDF_PATH=/data/document.pdf \
    RAG_INDEX_DIR=/indexes \
    RAG_MODEL_CACHE_DIR=/models \
    HF_HOME=/models \
    RAG_INDEX_AUTO_BUILD=false

RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system rag \
    && useradd --system --gid rag --home-dir /app --create-home rag

WORKDIR /app
RUN python -m pip install --no-cache-dir "uv==${UV_VERSION}"
COPY pyproject.toml uv.lock README LICENSE ./
RUN uv sync --locked --no-dev --no-editable
COPY src ./src
COPY agent_demo.py app.py ./
RUN uv sync --locked --no-dev \
    && mkdir -p /data /indexes /models \
    && chown -R rag:rag /app /indexes /models

USER rag
VOLUME ["/indexes", "/models"]
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["engineering-rag-health", "live"]
CMD ["engineering-rag-web", "--server.address=0.0.0.0", "--server.port=8501"]
