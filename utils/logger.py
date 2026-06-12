from pathlib import Path
from loguru import logger

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "ingestion.log"


def setup_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        LOG_FILE,
        rotation="5 MB",
        retention="10 days",
        encoding="utf-8",
        level="INFO",
    )

    logger.add(
        sink=lambda message: print(message, end=""),
        level="INFO",
    )

    return logger
