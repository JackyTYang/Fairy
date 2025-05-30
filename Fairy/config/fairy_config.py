import os
from enum import Enum

from dotenv import load_dotenv

from Fairy.config.model_config import CoreChatModelConfig, RAGChatModelConfig, RAGEmbedModelConfig, ModelConfig


class InteractionMode(Enum):
    Dialog = "DIALOG"
    Console = "CONSOLE"

class MobileControllerType(Enum):
    UIAutomator = "UI_AUTOMATOR"
    ADB = "ADB"

class ScreenPerceptionType(Enum):
    FVP = "FVP"
    SSIP = "SSIP"

class FairyConfig:
    def __init__(self,
                 model: CoreChatModelConfig,
                 rag_model: RAGChatModelConfig,
                 rag_embed_model: RAGEmbedModelConfig,
                 visual_prompt_model: ModelConfig,
                 adb_path,
                 temp_path=None,
                 screenshot_phone_path=None,
                 screenshot_filename=None,
                 action_executor_type: MobileControllerType = MobileControllerType.UIAutomator,
                 screenshot_getter_type: MobileControllerType = MobileControllerType.UIAutomator,
                 screen_perception_type: ScreenPerceptionType = ScreenPerceptionType.SSIP,
                 non_visual_mode: bool=False,
                 interaction_mode: InteractionMode=InteractionMode.Dialog,
                 manual_collect_app_info: bool=False,
                 reflection_policy: str='hybrid',
                 ):

        self.model_client = model.build()
        self.rag_model_client = rag_model.build()
        self.rag_embed_model_client = rag_embed_model.build()

        self.visual_prompt_model_config = visual_prompt_model

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
    
class FairyEnvConfig(FairyConfig):
    def __init__(self):
        load_dotenv()
        super().__init__(model=CoreChatModelConfig(
                              model_name=os.getenv("CORE_LMM_MODEL_NAME"),
                              model_temperature=0,
                              model_info={"vision": True, "function_calling": True, "json_output": True},
                              api_base=os.getenv("CORE_LMM_API_BASE"),
                              api_key=os.getenv("CORE_LMM_API_KEY")
                          ),
                          rag_model=RAGChatModelConfig(
                              model_name=os.getenv("RAG_LLM_API_NAME"),
                              model_temperature=0,
                              api_base=os.getenv("RAG_LLM_API_BASE"),
                              api_key=os.getenv("RAG_LLM_API_KEY")
                          ),
                          rag_embed_model=RAGEmbedModelConfig(
                              model_name=os.getenv("RAG_EMBED_MODEL_NAME")
                          ),
                          visual_prompt_model=ModelConfig(
                              model_name=os.getenv("VISUAL_PROMPT_LMM_API_NAME"),
                              api_base=os.getenv("VISUAL_PROMPT_LMM_API_BASE"),
                              api_key=os.getenv("VISUAL_PROMPT_LMM_API_KEY")
                          ),
                          adb_path=os.getenv("ADB_PATH"),
                          temp_path=os.getenv("TEMP_PATH"),
                          screenshot_phone_path=os.getenv("SCREEN_PHONE_PATH"),
                          screenshot_filename=os.getenv("SCREEN_FILENAME"),
                          action_executor_type= MobileControllerType(os.getenv("ACTION_EXECUTOR_TYPE")),
                          screenshot_getter_type = MobileControllerType(os.getenv("SCREENSHOT_GETTER_TYPE")),
                          screen_perception_type = ScreenPerceptionType(os.getenv("SCREEN_PERCEPTION_TYPE")),
                          interaction_mode = InteractionMode(os.getenv("INTERACTION_MODE")),
                          non_visual_mode=bool(os.getenv("NON_VISUAL_MODE")),
                          manual_collect_app_info=bool(os.getenv("MANUAL_COLLECT_APP_INFO")),
                          reflection_policy=os.getenv("REFLECTION_POLICY"))
    