import logging
import traceback
from logging.handlers import RotatingFileHandler
import time


def setup_logger():
    logger = logging.getLogger("process_logger")
    logger.setLevel(logging.ERROR)

    handler = RotatingFileHandler(
        "process_errors.log", maxBytes=50 * 1024 * 1024, backupCount=1
    )  # Ограничение в 50 МБ с 1 бэкапом
    handler.setLevel(logging.ERROR)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


def log_error(logger, process_name, exception):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    logger.error(f"Time: {timestamp} | Process: {process_name} | Error: {str(exception)}")
    traceback_str = ''.join(traceback.format_exc())
    logger.error(f"Traceback:\n{traceback_str}")
