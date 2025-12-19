"""
Explorer 模块

功能探索器，用于自动探索应用功能
"""

from .config import ExplorerConfig
from .entities import (
    ExplorationTarget,
    ExplorationStep,
    ExplorationPlan,
    ExplorationResult,
    PerceptionOutput,
    ExecutionSnapshot
)
from .explorer import FairyExplorer
from .logger import setup_logger, get_logger

__all__ = [
    # 配置
    "ExplorerConfig",

    # 实体
    "ExplorationTarget",
    "ExplorationStep",
    "ExplorationPlan",
    "ExplorationResult",
    "PerceptionOutput",
    "ExecutionSnapshot",

    # 核心类
    "FairyExplorer",

    # 日志
    "setup_logger",
    "get_logger"
]
