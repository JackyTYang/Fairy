"""
Explorer 日志配置

提供统一的日志配置，支持控制台和文件输出
"""

import sys
from pathlib import Path
from loguru import logger


def setup_logger(
    log_level: str = "INFO",
    log_file: Path = None,
    enable_console: bool = True,
    enable_file: bool = True
):
    """配置Explorer的日志系统

    Args:
        log_level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_file: 日志文件路径
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
    """
    # 移除默认处理器
    logger.remove()

    # 控制台输出
    if enable_console:
        logger.add(
            sys.stdout,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
                   "<level>{message}</level>",
            colorize=True
        )

    # 文件输出
    if enable_file and log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} | {message}",
            rotation="50 MB",
            retention="7 days",
            encoding="utf-8"
        )

    logger.info(f"日志系统已初始化，级别: {log_level}")


def get_logger(name: str):
    """获取命名logger

    Args:
        name: Logger名称

    Returns:
        logger实例
    """
    return logger.bind(name=name)
