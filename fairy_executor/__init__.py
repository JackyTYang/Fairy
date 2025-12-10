"""
Fairy Executor - 模块化的移动端自动化执行器

提供清晰的配置、执行、输出管理接口
"""

from .config import ExecutorConfig
from .executor import FairyExecutor
from .output import ExecutionOutput, OutputManager

__all__ = [
    'ExecutorConfig',
    'FairyExecutor',
    'ExecutionOutput',
    'OutputManager'
]

__version__ = '2.0.0'
