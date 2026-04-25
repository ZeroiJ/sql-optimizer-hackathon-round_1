FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY models.py .
COPY __init__.py .
COPY openenv.yaml .
COPY server/ server/
COPY scripts/ scripts/

RUN pip install --no-cache-dir \
    "openenv-core[core]>=0.2.2" \
    "fastapi>=0.115.0" \
    "pydantic>=2.0.0" \
    "uvicorn>=0.24.0" \
    "requests>=2.31.0" \
    "huggingface-hub>=0.20.0" \
    "transformers>=4.36.0" \
    "python-dotenv>=1.0.0" \
    "psycopg2-binary>=2.9.0"

ENV PYTHONPATH=/app

EXPOSE 7860

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
