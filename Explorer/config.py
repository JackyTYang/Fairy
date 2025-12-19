"""
Explorer 配置模块

管理Explorer的所有配置，从.env文件加载
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 加载 Explorer/.env 文件
explorer_env_path = Path(__file__).parent / ".env"
if explorer_env_path.exists():
    load_dotenv(explorer_env_path)


@dataclass
class ExplorerConfig:
    """Explorer配置类

    从Explorer/.env文件加载配置

    Attributes:
        # LLM配置（用于计划生成和重新规划）
        llm_model_name: LLM模型名称
        llm_api_key: API密钥
        llm_api_base: API基础URL
        llm_temperature: 温度参数

        # 视觉模型配置（用于Perceptor）
        visual_model_name: 视觉模型名称
        visual_api_key: API密钥
        visual_api_base: API基础URL

        # ADB配置
        adb_path: ADB可执行文件路径
        device_id: 设备ID（可选）

        # 输出配置
        output_dir: 输出根目录

        # 执行配置
        max_plan_steps: 单次计划的最大步骤数
        replan_on_every_step: 是否每步都重新规划
        replan_interval: 如果不是每步都规划，则每N步重新规划
        max_exploration_steps: 最大探索步骤数（防止无限循环）
    """
    # LLM配置（无默认值）
    llm_model_name: str
    llm_api_key: str
    llm_api_base: str

    # 视觉模型配置（无默认值）
    visual_model_name: str
    visual_api_key: str
    visual_api_base: str

    # ADB配置（无默认值）
    adb_path: str

    # 以下字段有默认值，必须放在后面
    llm_temperature: float = 0
    device_id: Optional[str] = None
    output_dir: Path = Path("output/exploration")
    max_plan_steps: int = 20
    replan_on_every_step: bool = True  # 默认每步都重新规划
    replan_interval: int = 1  # 如果不是每步都规划，则间隔
    max_exploration_steps: int = 50  # 防止无限循环

    @classmethod
    def from_env(cls) -> "ExplorerConfig":
        """从Explorer/.env文件加载配置

        Returns:
            ExplorerConfig实例

        Raises:
            ValueError: 如果必需的环境变量未设置
        """
        # 必需的环境变量
        required_vars = [
            "EXPLORER_LLM_MODEL_NAME",
            "EXPLORER_LLM_API_KEY",
            "EXPLORER_LLM_API_BASE",
            "EXPLORER_VISUAL_MODEL_NAME",
            "EXPLORER_VISUAL_API_KEY",
            "EXPLORER_VISUAL_API_BASE",
            "EXPLORER_ADB_PATH"
        ]

        # 检查必需变量
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(
                f"缺少必需的环境变量: {', '.join(missing_vars)}\n"
                f"请在 Explorer/.env 文件中配置这些变量"
            )

        return cls(
            # LLM配置
            llm_model_name=os.getenv("EXPLORER_LLM_MODEL_NAME"),
            llm_api_key=os.getenv("EXPLORER_LLM_API_KEY"),
            llm_api_base=os.getenv("EXPLORER_LLM_API_BASE"),
            llm_temperature=float(os.getenv("EXPLORER_LLM_TEMPERATURE", "0")),

            # 视觉模型配置
            visual_model_name=os.getenv("EXPLORER_VISUAL_MODEL_NAME"),
            visual_api_key=os.getenv("EXPLORER_VISUAL_API_KEY"),
            visual_api_base=os.getenv("EXPLORER_VISUAL_API_BASE"),

            # ADB配置
            adb_path=os.getenv("EXPLORER_ADB_PATH"),
            device_id=os.getenv("EXPLORER_DEVICE_ID"),

            # 输出配置
            output_dir=Path(os.getenv("EXPLORER_OUTPUT_DIR", "output/exploration")),

            # 执行配置
            max_plan_steps=int(os.getenv("EXPLORER_MAX_PLAN_STEPS", "20")),
            replan_on_every_step=os.getenv("EXPLORER_REPLAN_ON_EVERY_STEP", "true").lower() == "true",
            replan_interval=int(os.getenv("EXPLORER_REPLAN_INTERVAL", "1")),
            max_exploration_steps=int(os.getenv("EXPLORER_MAX_EXPLORATION_STEPS", "50"))
        )

    def __str__(self) -> str:
        """格式化输出配置信息（隐藏API密钥）"""
        return (
            f"ExplorerConfig:\n"
            f"  LLM Model: {self.llm_model_name}\n"
            f"  Visual Model: {self.visual_model_name}\n"
            f"  ADB Path: {self.adb_path}\n"
            f"  Device ID: {self.device_id or 'Auto-detect'}\n"
            f"  Output Dir: {self.output_dir}\n"
            f"  Replan on Every Step: {self.replan_on_every_step}\n"
            f"  Max Exploration Steps: {self.max_exploration_steps}"
        )
