from PIL import Image

from Fairy.info_entity import ScreenFileInfo
from .compressXML import get_compress_xml
from .compressXML import is_keyboard_active
from .entity import AdaptiveSemanticScreenModelingInfo


class AdaptiveSemanticScreenModeling:
    def __init__(self):
        pass

    def get_perception_infos(self, screenshot_file_info: ScreenFileInfo, ui_hierarchy_xml):
        width, height = Image.open(screenshot_file_info.get_screenshot_fullpath()).size
        keyboard_status = is_keyboard_active(ui_hierarchy_xml,height)
        perception_infos = get_compress_xml(ui_hierarchy_xml)

        return screenshot_file_info, AdaptiveSemanticScreenModelingInfo(width, height, perception_infos, keyboard_status)
