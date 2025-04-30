import os
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
                 manual_collect_app_info: bool=False,
                 reflection_policy: str='hybrid',
                 ):

        self.model_client = model.build()
        self.rag_model_client = rag_model.build()
        self.rag_embed_model_client = rag_embed_model.build()

        self._adb_path = adb_path
        self.device = None

        # path of local temporary storage
        self.temp_path = "tmp" if temp_path is None else temp_path
        os.makedirs(self.temp_path, exist_ok=True)

        self.task_temp_path = None

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
        self.manual_collect_app_info = manual_collect_app_info

        self.reflection_policy = reflection_policy

    def get_user_mobile_record_path(self) -> str:
        os.makedirs(os.path.join(self.temp_path, self.device, "record"), exist_ok=True)
        return str(os.path.join(self.temp_path, self.device, "record"))

    def get_user_mobile_app_info_path(self):

        return os.path.join(self.get_user_mobile_record_path(), "app_info.json")

    def get_screenshot_temp_path(self):
        return os.path.join(self.task_temp_path, "screenshot")

    def get_log_temp_path(self):
        return os.path.join(self.task_temp_path, "log")

    def get_short_time_memory_restore_point_path(self):
        return os.path.join(self.task_temp_path, "STM_restore_point")

    def get_adb_path(self):
        return (self._adb_path + f" -s {self.device}") if self.device is not None else self._adb_path