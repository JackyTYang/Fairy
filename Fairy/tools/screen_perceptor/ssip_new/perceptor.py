import asyncio

from PIL import Image

from Fairy.config.model_config import ModelConfig
from Fairy.info_entity import ScreenFileInfo
from screen_AT import ScreenAccessibilityTree
from visual_description_generator import VisualDescriptionGenerator


class ScreenStructuredInfoPerception:
    def __init__(self, visual_prompt_model_config):
        self.image_description_generator = VisualDescriptionGenerator(visual_prompt_model_config)

    async def get_perception_infos(self, screenshot_file_info: ScreenFileInfo, ui_hierarchy_xml, need_vision_desc=True):
        at = ScreenAccessibilityTree(ui_hierarchy_xml)
        # 补全图像节点
        if need_vision_desc:
            node_bounds_list = at.get_nodes_need_visual_desc()
            visual_description_map = await self.image_description_generator.generate_visual_description(screenshot_file_info, node_bounds_list)
            at.set_visual_desc_to_nodes(visual_description_map)

        page_desc = at.get_page_description()
        for a in page_desc:
            print(a)

        # # ocr过滤被遮盖节点
        # ocr_filter_xml = self.ocr_filter.filter(ui_hierarchy_xml,screenshot_file_info)
        # # 判断keyboard是否激活
        # width, height = Image.open(screenshot_file_info.get_screenshot_fullpath()).size
        # keyboard_status = is_keyboard_active(ocr_filter_xml, height)
        # # imageview添加描述信息
        # xml = self.screen_icon_perception.get_icon_perception(screenshot_file_info, ocr_filter_xml)
        # # xml清洗 去除冗余信息
        # compressed_xml = get_compress_xml(xml)
        #
        # return screenshot_file_info, AdaptiveSemanticScreenModelingInfo(width, height,
        #                                                                 [ui_hierarchy_xml, compressed_xml],
        #                                                                 keyboard_status)

async def main():
    with open("E.xml", "r", encoding="utf-8") as f:
        ui_hierarchy_xml = f.read()  # 读取整个文件为字符串

    ssip = ScreenStructuredInfoPerception(ModelConfig(
        model_name="qwen-vl-plus",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-d4e50bd7e07747b4827611c28da95c23",
    ))
    screenshot_file_info = ScreenFileInfo("L://ProgramProjects//FairyFamily//FairyNext//tmp//SSIP//screenshot//","screenshot","png", "1750128489")
    await ssip.get_perception_infos(screenshot_file_info, ui_hierarchy_xml)

if __name__ == '__main__':
    asyncio.run(main())