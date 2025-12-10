"""
配置管理模块

提供统一的配置接口，支持从环境变量、字典、文件加载配置
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv


@dataclass
class ModelConfig:
    """模型配置"""
    model_name: str
    api_key: str
    api_base: str
    temperature: float = 0.0

    @classmethod
    def from_env(cls, prefix: str) -> 'ModelConfig':
        """从环境变量加载配置

        Args:
            prefix: 环境变量前缀，如 'CORE_LMM' 会读取 CORE_LMM_MODEL_NAME 等
        """
        return cls(
            model_name=os.getenv(f"{prefix}_MODEL_NAME"),
            api_key=os.getenv(f"{prefix}_API_KEY"),
            api_base=os.getenv(f"{prefix}_API_BASE"),
            temperature=float(os.getenv(f"{prefix}_TEMPERATURE", "0.0"))
        )


@dataclass
class DeviceConfig:
    """设备配置"""
    device_id: str
    temp_path: str = "tmp"
    screenshot_phone_path: str = "/sdcard"
    screenshot_filename: str = "screenshot"

    def __post_init__(self):
        """确保临时目录存在"""
        Path(self.temp_path).mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> 'DeviceConfig':
        """从环境变量加载设备配置"""
        return cls(
            device_id=os.getenv("DEVICE_ID", ""),
            temp_path=os.getenv("TEMP_PATH", "tmp"),
            screenshot_phone_path=os.getenv("SCREEN_PHONE_PATH", "/sdcard"),
            screenshot_filename=os.getenv("SCREEN_FILENAME", "screenshot")
        )


@dataclass
class PerceptionConfig:
    """屏幕感知配置"""
    visual_model: Optional[Any] = None  # Fairy ModelConfig对象
    text_summary_model: Optional[Any] = None  # Fairy ModelConfig对象
    non_visual_mode: bool = False
    save_marked_images: bool = True

    @classmethod
    def from_env(cls) -> 'PerceptionConfig':
        """从环境变量加载感知配置"""
        from Fairy.config.model_config import ModelConfig as FairyModelConfig

        # 视觉模型配置
        visual_model = FairyModelConfig(
            model_name=os.getenv("VISUAL_PROMPT_LMM_API_NAME"),
            model_temperature=0,
            model_info={"vision": True, "function_calling": False, "json_output": False},
            api_base=os.getenv("VISUAL_PROMPT_LMM_API_BASE"),
            api_key=os.getenv("VISUAL_PROMPT_LMM_API_KEY")
        )

        # 文本摘要模型配置
        text_summary_model = FairyModelConfig(
            model_name=os.getenv("RAG_LLM_API_NAME"),
            model_temperature=0,
            model_info={"vision": False, "function_calling": False, "json_output": False},
            api_base=os.getenv("RAG_LLM_API_BASE"),
            api_key=os.getenv("RAG_LLM_API_KEY")
        )

        return cls(
            visual_model=visual_model,
            text_summary_model=text_summary_model,
            non_visual_mode=os.getenv("NON_VISUAL_MODE", "False").lower() == "true",
            save_marked_images=os.getenv("SAVE_MARKED_IMAGES", "True").lower() == "true"
        )


@dataclass
class OutputConfig:
    """输出配置"""
    output_dir: Path = field(default_factory=lambda: Path("output"))
    save_screenshots: bool = True
    save_marked_images: bool = True
    save_logs: bool = True
    log_level: str = "INFO"

    def __post_init__(self):
        """确保输出目录存在"""
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (self.output_dir / "screenshots").mkdir(exist_ok=True)
        (self.output_dir / "marked_images").mkdir(exist_ok=True)
        (self.output_dir / "logs").mkdir(exist_ok=True)

    @classmethod
    def from_env(cls) -> 'OutputConfig':
        """从环境变量加载输出配置"""
        return cls(
            output_dir=Path(os.getenv("OUTPUT_DIR", "output")),
            save_screenshots=os.getenv("SAVE_SCREENSHOTS", "True").lower() == "true",
            save_marked_images=os.getenv("SAVE_MARKED_IMAGES", "True").lower() == "true",
            save_logs=os.getenv("SAVE_LOGS", "True").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )


@dataclass
class ExecutorConfig:
    """执行器总配置

    统一管理所有配置项，支持多种加载方式

    Examples:
        # 从环境变量加载
        config = ExecutorConfig.from_env()

        # 从字典加载
        config = ExecutorConfig.from_dict({
            'device': {'device_id': 'emulator-5554'},
            'core_model': {'model_name': 'gpt-4', ...}
        })

        # 直接构造
        config = ExecutorConfig(
            device=DeviceConfig(device_id='emulator-5554'),
            core_model=ModelConfig(...)
        )
    """
    device: DeviceConfig
    core_model: ModelConfig
    perception: PerceptionConfig
    output: OutputConfig

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> 'ExecutorConfig':
        """从环境变量加载完整配置

        Args:
            env_file: .env文件路径，如果不指定则使用当前目录的.env
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        return cls(
            device=DeviceConfig.from_env(),
            core_model=ModelConfig.from_env("CORE_LMM"),
            perception=PerceptionConfig.from_env(),
            output=OutputConfig.from_env()
        )

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ExecutorConfig':
        """从字典加载配置

        Args:
            config_dict: 配置字典，格式如：
                {
                    'device': {'device_id': '...'},
                    'core_model': {'model_name': '...', ...},
                    'perception': {...},
                    'output': {...}
                }
        """
        return cls(
            device=DeviceConfig(**config_dict.get('device', {})),
            core_model=ModelConfig(**config_dict['core_model']),
            perception=PerceptionConfig(**config_dict.get('perception', {})),
            output=OutputConfig(**config_dict.get('output', {}))
        )

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            'device': self.device.__dict__,
            'core_model': self.core_model.__dict__,
            'perception': {
                'non_visual_mode': self.perception.non_visual_mode,
                'save_marked_images': self.perception.save_marked_images
            },
            'output': self.output.__dict__
        }
