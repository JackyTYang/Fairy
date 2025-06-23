import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from Fairy.config.model_config import ModelConfig
from Fairy.entity.info_entity import ScreenFileInfo
from Fairy.tools.screen_perceptor.ssip_new.perceptor import ScreenStructuredInfoPerception

load_dotenv(dotenv_path=Path('../../.env'))

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

async def test_with_case_mcdonalds_1():
    with open("test_case_mcdonalds/mcdonalds_app_case_1_accessibility_tree.xml", "r", encoding="utf-8") as f:
        ui_hierarchy_xml = f.read()

    ssip = ScreenStructuredInfoPerception(visual_prompt_model_config, text_summarization_model_config)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    screenshot_file_info = ScreenFileInfo(f"{current_dir}/test_case_mcdonalds","mcdonalds_app_case_1_screenshot","png", "1750128489")

    perception_infos = await ssip.get_perception_infos(screenshot_file_info, ui_hierarchy_xml, target_app="com.mcdonalds.gma.cn", need_vision_desc=True)
    print(perception_infos)



if __name__ == '__main__':
    asyncio.run(test_with_case_mcdonalds_1())