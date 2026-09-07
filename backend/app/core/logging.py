"""
Structured logging configuration.

Design decision: use structlog instead of the stdlib logging module directly.

Why this matters for BeautyAI specifically:
- We will eventually need to trace a single conversation across multiple
  LangGraph nodes, tool calls, and HTTP requests (see docs/architecture.md,
  Observability section). That requires every log line to carry
  request_id / conversation_id / user_id as structured fields, not buried
  inside a free-text message.
- structlog lets us bind context once (e.g. at the start of a request) and
  have it automatically attached to every subsequent log call on that
  "thread" of execution, without threading the values through every
  function signature.
- JSON output in staging/production is trivial to ship into a log
  aggregator (e.g. CloudWatch, Loki, Datadog) later; human-readable
  console output is nicer for local development. We toggle via
  settings.log_json.

This module only sets up *logging infrastructure*. Sprint 2+ will add a
request-ID middleware that binds `request_id` into the context for the
duration of each HTTP request.
"""

import logging
import sys

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level.upper(),
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_json:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to a module/component name."""
    return structlog.get_logger(name)
