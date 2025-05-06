from PIL import Image

from Fairy.info_entity import ScreenFileInfo
from .compressXML import get_compress_xml
from .compressXML import is_keyboard_active
from .entity import AdaptiveSemanticScreenModelingInfo
from .ocr_filter import OCRFilterTool
from .screen_icon_perception import ScreenIconPerception


class AdaptiveSemanticScreenModeling:
    def __init__(self):
        self.screen_icon_perception = ScreenIconPerception()
        self.ocr_filter = OCRFilterTool()

    def get_perception_infos(self, screenshot_file_info: ScreenFileInfo, ui_hierarchy_xml):
        # ocr过滤被遮盖节点
        ui_hierarchy_xml = self.ocr_filter.filter(ui_hierarchy_xml,screenshot_file_info)
        # 判断keyboard是否激活
        width, height = Image.open(screenshot_file_info.get_screenshot_fullpath()).size
        keyboard_status = is_keyboard_active(ui_hierarchy_xml, height)
        # imageview添加描述信息
        xml = self.screen_icon_perception.get_icon_perception(screenshot_file_info, ui_hierarchy_xml)
        # xml清洗 去除冗余信息
        perception_infos = get_compress_xml(xml)

        return screenshot_file_info, AdaptiveSemanticScreenModelingInfo(width, height, perception_infos,
                                                                        keyboard_status)
