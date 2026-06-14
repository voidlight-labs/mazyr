import logging
import os
import stat
from logging.handlers import RotatingFileHandler

from mazyr.infrastructure.paths import MAZYR_HOME

LOG_DIR = MAZYR_HOME / "logs"
LOG_FILE = LOG_DIR / "mazyr.log"
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 3

# Owner-only permissions for log directory and files.
_LOG_DIR_MODE = stat.S_IRWXU  # 0o700
_LOG_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0o600

_initialized = False


def get_logger(name: str) -> logging.Logger:
    global _initialized

    logger = logging.getLogger(name)

    if _initialized:
        return logger

    os.makedirs(LOG_DIR, exist_ok=True)
    LOG_DIR.chmod(_LOG_DIR_MODE)

    handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    # Ensure the active log file and any rotated backups are owner-only.
    for log_path in LOG_DIR.glob("mazyr.log*"):
        log_path.chmod(_LOG_FILE_MODE)

    _initialized = True
    return logger
