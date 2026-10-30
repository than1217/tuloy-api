import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_PATH = Path(__file__).resolve().parent / "logs" / "tuloy-api.log"
MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5


def configure_logging():
    logger = logging.getLogger("tuloy_api")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )

        file_handler = RotatingFileHandler(
            LOG_PATH,
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
