# Nova in a container. The SQLite database lives on the /data volume
# (NOVA_DB_PATH), never in the container's writable layer, so it survives
# `docker compose down && docker compose up` and Fly.io redeploys.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NOVA_DB_PATH=/data/nova.db

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# The app runs as an unprivileged user that owns only the data directory.
# docker-entrypoint.sh starts as root just to chown /data (Fly.io mounts
# volumes root-owned), then drops to nova before starting Streamlit.
RUN useradd --create-home --uid 1000 nova \
    && mkdir -p /data \
    && chown nova:nova /data \
    && sed -i 's/\r$//' docker-entrypoint.sh \
    && chmod +x docker-entrypoint.sh
VOLUME ["/data"]

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# 0.0.0.0 inside the container; docker-compose.yml publishes the port on
# 127.0.0.1 only, and on Fly.io the proxy in front handles HTTPS.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
