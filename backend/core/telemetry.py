"""Observabilidade do próprio Sentinel: métricas Prometheus e logs estruturados (JSON)."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

REGISTRY = CollectorRegistry(auto_describe=True)

INCIDENTS = Counter("sentinel_incidents_total", "Incidentes abertos", ["type", "sev", "source"], registry=REGISTRY)
TRANSITIONS = Counter("sentinel_incident_transitions_total", "Mudanças de status", ["to"], registry=REGISTRY)
DECISIONS = Counter("sentinel_decisions_total", "Decisões sobre correções", ["decision", "auto"], registry=REGISTRY)
REMEDIATIONS = Counter("sentinel_remediations_total", "Correções aplicadas", ["action", "result"], registry=REGISTRY)
AI_CALLS = Counter("sentinel_ai_calls_total", "Chamadas de IA", ["provider", "outcome"], registry=REGISTRY)
AI_LATENCY = Histogram(
    "sentinel_ai_latency_seconds",
    "Duração das chamadas de IA",
    ["provider"],
    buckets=(1, 2, 5, 10, 20, 40, 80, 160, 300),
    registry=REGISTRY,
)
DETECTIONS = Counter("sentinel_detections_total", "Sinais do Monitor", ["type", "outcome"], registry=REGISTRY)
OPEN_INCIDENTS = Gauge("sentinel_open_incidents", "Incidentes abertos agora", ["sev"], registry=REGISTRY)
WS_CLIENTS = Gauge("sentinel_websocket_clients", "Clientes conectados na telemetria", registry=REGISTRY)


def render() -> bytes:
    return generate_latest(REGISTRY)


class JsonFormatter(logging.Formatter):
    """Uma linha JSON por evento: pronto para Loki, Elasticsearch ou CloudWatch."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_logging() -> None:
    """LOG_FORMAT=json para produção; texto legível no desenvolvimento."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    if os.getenv("LOG_FORMAT", "text").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("httpx", "urllib3", "kubernetes"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
