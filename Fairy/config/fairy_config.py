from enum import Enum

from Citlali.models.openai.client import OpenAIChatClient
from Fairy.config.model_config import CoreChatModelConfig, RAGChatModelConfig, RAGEmbedModelConfig


class InteractionMode(Enum):
    Dialog = 1
    Console = 2

class MobileControllerType(Enum):
    UIAutomator = 1
    ADB = 2

class ScreenPerceptionType(Enum):
    FVP = 1
    ASSM = 2

class FairyConfig:
    def __init__(self,
                 model: CoreChatModelConfig,
                 rag_model: RAGChatModelConfig,
                 rag_embed_model: RAGEmbedModelConfig,
                 adb_path,
                 temp_path=None,
                 screenshot_phone_path=None,
                 screenshot_filename=None,
                 action_executor_type: MobileControllerType = MobileControllerType.UIAutomator,
                 screenshot_getter_type: MobileControllerType = MobileControllerType.UIAutomator,
                 screen_perception_type: ScreenPerceptionType = ScreenPerceptionType.ASSM,
                 non_visual_mode: bool=False,
                 interaction_mode: InteractionMode=InteractionMode.Dialog,
                 ):

        self.model_client = model.build()
        self.rag_model_client = rag_model.build()
        self.rag_embed_model_client = rag_embed_model.build()

        self._adb_path = adb_path
        self.device = None

        # path of local temporary storage
        self.temp_path = "tmp" if temp_path is None else temp_path

        # path of screenshot storage on mobile phone
        self.screenshot_phone_path = "/sdcard" if screenshot_phone_path is None else screenshot_phone_path

        # filename of screenshot
        self.screenshot_filename = "screenshot" if screenshot_filename is None else screenshot_filename

        # execution strategy
        self.action_executor_type = action_executor_type # default action executor type
        self.screenshot_getter_type = screenshot_getter_type  # default screenshot getter type
        self.screen_perception_type = screen_perception_type # default screen_perception_type
        self.non_visual_mode = non_visual_mode
        self.interaction_mode = interaction_mode

    def get_screenshot_temp_path(self):
        return self.temp_path + "/screenshot"

    def get_log_temp_path(self):
        return self.temp_path + "/log"

    def get_adb_path(self):
        return (self._adb_path + f" -s {self.device}") if self.device is not None else self._adb_path