import logging
import structlog
import re
from typing import Any

PATTERNS_SEGREDO = [
    re.compile(r"(password|senha|api_key|jwt_secret|pwd)\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"sk-ant-[\w-]+"),
    re.compile(r"sk-[\w-]{20,}"),
]


def filtrar_segredos(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
    for k, v in list(event_dict.items()):
        if isinstance(v, str):
            for p in PATTERNS_SEGREDO:
                v = p.sub(r"\1=***", v) if p.groups else p.sub("***", v)
            event_dict[k] = v
    return event_dict


def configurar_logging() -> None:
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            filtrar_segredos,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger("apolo")
