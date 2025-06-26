import asyncio
import os
import time
from loguru import logger
from dotenv import load_dotenv

from Citlali.core.runtime import CitlaliRuntime
from Fairy.config.fairy_config import FairyConfig, MobileControllerType, ScreenPerceptionType
from Fairy.config.model_config import ModelConfig
from Fairy.entity.message_entity import EventMessage
from Fairy.tools.screen_perceptor.screen_perceptor import ScreenPerceptor
from pathlib import Path

from Fairy.entity.type import EventType, EventChannel, EventStatus

load_dotenv(dotenv_path=Path('../.env'))

visual_prompt_model_config = ModelConfig(
    model_name="qwen-vl-plus",
    api_base=os.getenv("ALI_API_BASE"),
    api_key=os.getenv("ALI_API_KEY"),
)

text_summarization_model_config = ModelConfig(
    model_name="qwen-turbo",
    api_base=os.getenv("ALI_API_BASE"),
    api_key=os.getenv("ALI_API_KEY"),
)

async def test_with_current_screen():
    _config = FairyConfig(model = None,
                 rag_model = None,
                 rag_embed_model = None,
                 visual_prompt_model=visual_prompt_model_config,
                 text_summarization_model=text_summarization_model_config,
                 adb_path = "C:/Users/neosunjz/AppData/Local/Android/Sdk/platform-tools/adb.exe",
                 temp_path=None,
                 screenshot_phone_path=None,
                 screenshot_filename=None,
                 action_executor_type = MobileControllerType.UIAutomator,
                 screenshot_getter_type = MobileControllerType.UIAutomator,
                 screen_perception_type = ScreenPerceptionType.SSIP,
                 non_visual_mode=False)

    # 指定设备，创建临时文件夹
    _config.device = os.getenv("DEVICE")
    _config.task_temp_path = f"{_config.temp_path}/Screen_Perceptor_Test_{time.strftime('%Y%m%d%H%M%S', time.localtime())}"
    os.mkdir(_config.task_temp_path)
    os.mkdir(_config.get_screenshot_temp_path())
    os.mkdir(_config.get_log_temp_path())
    # 配置日志
    logger.add(_config.get_log_temp_path() + "/screen_perception_log.log", filter=lambda x: x["extra"].get("log_tag") == "screen_perception", level="DEBUG")

    runtime = CitlaliRuntime()
    runtime.run()
    runtime.register(lambda: ScreenPerceptor(runtime, _config))
    await runtime.publish(EventChannel.APP_CHANNEL, EventMessage(EventType.ActionExecution, EventStatus.DONE))
    await runtime.stop()

if __name__ == '__main__':
    asyncio.run(test_with_current_screen())