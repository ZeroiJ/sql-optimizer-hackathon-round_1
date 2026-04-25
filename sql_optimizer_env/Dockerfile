FROM python:3.10-slim

WORKDIR /app

# Keep image lean while supporting psycopg2-binary runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

# Minimal runtime deps for serving the OpenEnv environment.
RUN pip install --no-cache-dir --default-timeout=300 --retries 10 \
    "openenv-core[core]>=0.2.2" \
    "fastapi>=0.115.0" \
    "pydantic>=2.0.0" \
    "uvicorn>=0.24.0" \
    "requests>=2.31.0" \
    "python-dotenv>=1.0.0" \
    "psycopg2-binary>=2.9.0"

ENV PYTHONPATH=/app
EXPOSE 7860

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
