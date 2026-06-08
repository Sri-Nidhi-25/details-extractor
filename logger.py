"""Logging configuration for the whole project."""

import logging
import sys


def setup_logger(name: str | None = None, level: int = logging.INFO) -> logging.Logger:
    """Set up a logger with consistent format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# Default root logger for the project
logger = setup_logger("document_extractor")