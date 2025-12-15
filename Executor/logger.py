"""
日志管理模块

使用loguru提供统一、美观的日志输出
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
    """配置日志系统

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        log_file: 日志文件路径
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
    """
    # 移除默认handler
    logger.remove()

    # 控制台输出 - 美观的格式
    if enable_console:
        logger.add(
            sys.stdout,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            level=log_level,
            colorize=True
        )

    # 文件输出 - 详细的格式
    if enable_file and log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",  # 文件记录所有级别
            rotation="10 MB",  # 日志轮转
            retention="7 days",  # 保留7天
            compression="zip"  # 压缩旧日志
        )

    return logger


def get_logger(name: str = None):
    """获取logger实例

    Args:
        name: logger名称

    Returns:
        logger实例
    """
    if name:
        return logger.bind(name=name)
    return logger
