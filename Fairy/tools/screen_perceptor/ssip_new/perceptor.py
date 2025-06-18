import asyncio
from copy import deepcopy

from loguru import logger

from Fairy.config.model_config import ModelConfig
from Fairy.info_entity import ScreenFileInfo
from Fairy.tools.screen_perceptor.ssip_new.entity import SSIPInfo
from Fairy.tools.screen_perceptor.ssip_new.llm_tools.text_summarizer import TextSummarizer
from Fairy.tools.screen_perceptor.ssip_new.tools import draw_transparent_boxes_with_labels
from Fairy.tools.screen_perceptor.ssip_new.screen_AT import ScreenAccessibilityTree
from Fairy.tools.screen_perceptor.ssip_new.llm_tools.visual_description_generator import VisualDescriptionGenerator

class ScreenStructuredInfoPerception:
    def __init__(self, visual_prompt_model_config, text_summarize_model_config):
        self.image_description_generator = VisualDescriptionGenerator(visual_prompt_model_config) if visual_prompt_model_config is not None else None
        self.text_summarizer = TextSummarizer(text_summarize_model_config) if text_summarize_model_config is not None else None

    async def get_perception_infos(self, raw_screenshot_file_info: ScreenFileInfo, ui_hierarchy_xml, need_vision_desc=True, use_screenshot_mark=True, use_clickable_node_summaries=True):
        at = ScreenAccessibilityTree(ui_hierarchy_xml, only_app=True)

        # 确定宽高
        screenshot_image = raw_screenshot_file_info.get_screenshot_PILImage_file()
        width, height = screenshot_image.size

        # 启用图像标记
        if use_screenshot_mark:
            node_bounds_list = at.get_nodes_clickable(set_mark=True)
            screenshot_image_marked = draw_transparent_boxes_with_labels(screenshot_image, node_bounds_list)
            # 构建新的截屏文件对象
            screenshot_file_info = deepcopy(raw_screenshot_file_info)
            screenshot_file_info.file_extra_name = "marked"
            screenshot_image_marked.save(screenshot_file_info.get_screenshot_fullpath())
        else:
            screenshot_file_info = raw_screenshot_file_info

        # 补全图像节点
        if need_vision_desc and self.image_description_generator is not None:
            node_bounds_list = at.get_nodes_need_visual_desc()
            visual_description_map = await self.image_description_generator.generate_visual_description(raw_screenshot_file_info, node_bounds_list)
            at.set_visual_desc_to_nodes(visual_description_map)
        elif need_vision_desc:
            logger.bind(log_tag="fairy_sys").warning("[Screen Perception] Image node complementation enabled but no 'visual_prompt_model_config' provided, so image complementation is NOT available!")

        # 启用节点总结
        if use_clickable_node_summaries and self.text_summarizer is not None:
            page_desc = await at.get_page_description(self.text_summarizer.summarize_text)
        elif use_clickable_node_summaries:
            logger.bind(log_tag="fairy_sys").warning("[Screen Perception] Clickable node summaries enabled but no 'text_summarize_model_config' provided, so summaries are not available!")
            page_desc = await at.get_page_description()
        else:
            page_desc = await at.get_page_description()

        return screenshot_file_info, SSIPInfo(width, height, page_desc, keyboard_status)

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
    ), ModelConfig(
            model_name="qwen-turbo",
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key="sk-d4e50bd7e07747b4827611c28da95c23",
        ))
    screenshot_file_info = ScreenFileInfo("L://ProgramProjects//FairyFamily//FairyNext//tmp//SSIP//screenshot//","screenshot","png", "1750128489")
    await ssip.get_perception_infos(screenshot_file_info, ui_hierarchy_xml, need_vision_desc=True)

if __name__ == '__main__':
    asyncio.run(main())