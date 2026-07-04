"""日志模块"""
import logging
import os
from logging.handlers import RotatingFileHandler

from app.config import config


def setup_logger(name: str = "keeper") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # 文件
    try:
        file_handler = RotatingFileHandler(
            config.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass

    return logger


logger = setup_logger()
