from copy import deepcopy

from loguru import logger

from Fairy.entity.info_entity import ScreenFileInfo
from Fairy.entity.log_template import LogTemplate, WorkerType, LogEventType
from Fairy.tools.screen_perceptor.ssip_new.entity import SSIPInfo
from Fairy.tools.screen_perceptor.ssip_new.llm_tools.text_summarizer import TextSummarizer
from Fairy.tools.screen_perceptor.ssip_new.tools import draw_transparent_boxes_with_labels
from Fairy.tools.screen_perceptor.ssip_new.screen_AT import ScreenAccessibilityTree
from Fairy.tools.screen_perceptor.ssip_new.llm_tools.visual_description_generator import VisualDescriptionGenerator

class ScreenStructuredInfoPerception:
    def __init__(self, visual_prompt_model_config, text_summarization_model_config):
        self.image_description_generator = VisualDescriptionGenerator(visual_prompt_model_config) if visual_prompt_model_config is not None else None
        self.text_summarizer = TextSummarizer(text_summarization_model_config) if text_summarization_model_config is not None else None
        self.log_t = LogTemplate(self,"ScreenStructuredInfoPerception")  # 日志模板

    async def get_perception_infos(self, raw_screenshot_file_info: ScreenFileInfo, ui_hierarchy_xml, non_visual_mode=False, target_app=None, use_clickable_node_summaries=True):
        logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerStart)("Screen Perception"))
        logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.Notice)("Analyzing Screen Accessibility Tree..."))
        at = ScreenAccessibilityTree(ui_hierarchy_xml, target_app = target_app)

        # 确定宽高
        screenshot_image = raw_screenshot_file_info.get_screenshot_PILImage_file()
        width, height = screenshot_image.size
        
        if non_visual_mode: # 如果是非图像模式（适用于不具备视觉能力的模型）
            SoM_mapping = None
            screenshot_file_info = raw_screenshot_file_info
        else:
            logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.Notice)("Adding Mark to screenshots..."))
            # 启用图像标记
            nodes_need_marked = at.get_nodes_need_marked(set_mark=True)

            SoM_mapping = {}
            SoM_mapping.update(nodes_need_marked['clickable']['node_center_list'])
            SoM_mapping.update(nodes_need_marked['scrollable']['node_bounds_list'])

            # 标记可点击元素 (红色框，标签在左上角)
            screenshot_image_marked = draw_transparent_boxes_with_labels(
                screenshot_image,
                nodes_need_marked["clickable"]["node_bounds_list"],
                label_position="top_left", box_color=(255, 0, 0, 180), font_box_background_color=(255, 0, 0, 160)
            )
            # 标记可滚动元素 (绿色框，标签在右上角)
            screenshot_image_marked = draw_transparent_boxes_with_labels(
                screenshot_image_marked,
                nodes_need_marked["scrollable"]["node_bounds_list"],
                label_position="top_right", box_color=(0, 255, 0, 180), font_box_background_color=(0, 255, 0, 160), line_width=5
            )

            # 构建新的截屏文件对象
            screenshot_file_info = deepcopy(raw_screenshot_file_info)
            screenshot_file_info.file_extra_name = "marked"
            screenshot_image_marked.convert("RGB").save(screenshot_file_info.get_screenshot_fullpath())

        # 如果是非图像模式（适用于不具备视觉能力的模型）
        if non_visual_mode:
            logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.Notice)("Fetching image node contents..."))
            # 补全图像节点
            if self.image_description_generator is not None:
                node_bounds_list = at.get_nodes_need_visual_desc()
                visual_description_map = await self.image_description_generator.generate_visual_description(raw_screenshot_file_info, node_bounds_list)
                at.set_visual_desc_to_nodes(visual_description_map)
            else:
                raise RuntimeError(self.log_t.log(LogEventType.MissingConfig)("'non_visual_mode=True'", "visual_prompt_model_config", "critical"))

            # 启用节点总结
            if use_clickable_node_summaries:
                logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.Notice)("Summarizing clickable node contents..."))
                if self.text_summarizer is not None:
                    page_desc = await at.get_page_description(self.text_summarizer.summarize_text)
                else:
                    logger.bind(log_tag="fairy_sys").error(self.log_t.log(LogEventType.MissingConfig)("'non_visual_mode=True' and 'use_clickable_node_summaries=True'", "text_summarization_model_config", "error"))
                    page_desc = await at.get_page_description()
            else:
                logger.bind(log_tag="fairy_sys").warning(self.log_t.log(LogEventType.FunctionNotActive)("Clickable Node Summaries", "not setting 'use_clickable_node_summaries'", "'use_clickable_node_summaries=True'"))
                page_desc = await at.get_page_description()

        else:
            logger.bind(log_tag="fairy_sys").warning(self.log_t.log(LogEventType.FunctionNotActive)("Screen Textualized Description", "not using 'non_visual_mode' policy", "'non_visual_mode=True'"))
            page_desc = None

        logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerCompleted)("Screen Perception"))
        return screenshot_file_info, SSIPInfo(width, height, [ui_hierarchy_xml, page_desc], non_visual_mode, SoM_mapping=SoM_mapping)

        # # ocr过滤被遮盖节点
        # ocr_filter_xml = self.ocr_filter.filter(ui_hierarchy_xml,screenshot_file_info)