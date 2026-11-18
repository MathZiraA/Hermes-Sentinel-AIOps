# Backend do Hermes Sentinel (build: docker build -f backend/Dockerfile .) (API, Monitor, MCP) — também é a imagem do agente de cluster (python -m agent).
FROM docker.io/library/python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LOG_FORMAT=json \
    OBSIDIAN_VAULT_PATH=/data/brain

WORKDIR /app
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin sentinel \
 && mkdir -p /data/brain /app/data && chown -R 10001:10001 /data /app

# Contexto do build: raiz do repositório (docker build -f backend/Dockerfile .)
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=10001:10001 backend/ .
# Runbooks oficiais entram na imagem; o resto do Hermes Brain fica no volume /data/brain
COPY --chown=10001:10001 ["obsidian-vault/06 - Runbooks/", "/app/brain-seed/"]

USER 10001
EXPOSE 8000 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/healthz', timeout=3)"
CMD ["sh", "-c", "mkdir -p '/data/brain/06 - Runbooks' && cp -n /app/brain-seed/*.md '/data/brain/06 - Runbooks/' 2>/dev/null; exec uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
