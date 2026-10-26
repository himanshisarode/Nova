# Nova in a container. The SQLite database lives on the /data volume
# (NOVA_DB_PATH), never in the container's writable layer, so it survives
# `docker compose down && docker compose up`.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NOVA_DB_PATH=/data/nova.db

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run as an unprivileged user that owns only the data directory.
RUN useradd --create-home --uid 1000 nova \
    && mkdir -p /data \
    && chown nova:nova /data
USER nova
VOLUME ["/data"]

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# 0.0.0.0 inside the container; docker-compose.yml publishes the port on
# 127.0.0.1 only, so the app isn't reachable from other machines.
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
