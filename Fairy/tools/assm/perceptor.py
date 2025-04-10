from Fairy.info_entity import ScreenFileInfo
from Fairy.tools.assm.entity import AdaptiveSemanticScreenModelingInfo


class AdaptiveSemanticScreenModeling:
    def __init__(self):
        pass


    def get_perception_infos(self, screenshot_file_info: ScreenFileInfo, ui_hierarchy_xml):

        return screenshot_file_info, AdaptiveSemanticScreenModelingInfo()