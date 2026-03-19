import structlog
import logging
import sys
from app.utils.config import get_settings

settings = get_settings()


def setup_logging():
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
    ]

    if settings.LOG_FORMAT == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)


def get_logger(name: str):
    return structlog.get_logger(name)


class AgentLogger:

    def __init__(self, session_id: str):
        self.logger = get_logger("agent")
        self.session_id = session_id

    def tool_called(self, tool_name: str, inputs: dict, duration_ms: float):
        self.logger.info(
            "tool_called",
            session_id=self.session_id,
            tool=tool_name,
            inputs=inputs,
            duration_ms=round(duration_ms, 2),
        )

    def tool_failed(self, tool_name: str, error: str, inputs: dict):
        self.logger.error(
            "tool_failed",
            session_id=self.session_id,
            tool=tool_name,
            error=error,
            inputs=inputs,
        )

    def decision_made(self, ticker: str, recommendation: str, confidence: float, duration_ms: float):
        self.logger.info(
            "decision_made",
            session_id=self.session_id,
            ticker=ticker,
            recommendation=recommendation,
            confidence=confidence,
            duration_ms=round(duration_ms, 2),
        )

    def guardrail_triggered(self, rule: str, detail: str):
        self.logger.warning(
            "guardrail_triggered",
            session_id=self.session_id,
            rule=rule,
            detail=detail,
        )