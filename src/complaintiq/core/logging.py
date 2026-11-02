import logging
import sys
from contextvars import ContextVar
from typing import Optional

request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "N/A"
        return True


def setup_logging(level: str = "INFO") -> None:
    log_format = "%(asctime)s | %(levelname)-7s | [%(request_id)s] | %(name)s:%(lineno)d - %(message)s"
    formatter = logging.Formatter(log_format)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    root_logger.addHandler(handler)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


logger = logging.getLogger("complaintiq")
