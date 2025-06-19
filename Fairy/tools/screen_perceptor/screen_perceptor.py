from loguru import logger

from Citlali.core.type import ListenerType
from Citlali.core.worker import Worker, listener
from Fairy.config.fairy_config import MobileControllerType, ScreenPerceptionType, FairyConfig
from Fairy.tools.mobile_controller.adb_tools.screenshot_tool import AdbMobileScreenshot
from Fairy.tools.mobile_controller.ui_automator_tools.screenshot_tool import UiAutomatorMobileScreenshot
from Fairy.info_entity import ScreenInfo
from Fairy.message_entity import EventMessage
from Fairy.tools.screen_perceptor.ssip_new.perceptor import ScreenStructuredInfoPerception
try:
    from Fairy.tools.screen_perceptor.fvp.perceptor import FineGrainedVisualPerceptor
except ImportError:
    logger.bind(log_tag="fairy_sys").warning(
        "Additional dependencies are required to use FVP."
    )
    FineGrainedVisualPerceptor = None
from Fairy.type import EventType


class ScreenPerceptor(Worker):
    def __init__(self, runtime, config: FairyConfig):
        super().__init__(runtime, "ScreenPerceptor", "ScreenPerceptor")

        self.screenshot_getter_type = config.screenshot_getter_type
        if self.screenshot_getter_type == MobileControllerType.ADB:
            self.screenshot_tool = AdbMobileScreenshot(config)
        elif self.screenshot_getter_type == MobileControllerType.UIAutomator:
            self.screenshot_tool = UiAutomatorMobileScreenshot(config)

        self.screen_perception_type = config.screen_perception_type
        if self.screen_perception_type == ScreenPerceptionType.SSIP and self.screenshot_getter_type == MobileControllerType.ADB:
            raise ValueError("SSIP requires uiautomator screenshot tool, but adb is used.")

        self.visual_prompt_model_config = config.visual_prompt_model_config
        self.text_summarization_model_config = config.text_summarization_model_config

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.ActionExecution_DONE)
    async def on_screen_percept(self, message: EventMessage, message_context):
        await self._on_screen_percept(message, message_context)

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.Task_CREATED)
    async def on_first_screen_percept(self, message: EventMessage, message_context):
        await self._on_screen_percept(message, message_context)

    async def _on_screen_percept(self, message: EventMessage, message_context):
        logger.bind(log_tag="fairy_sys").info("[Get Screenshot] and [Perception Information] Task in progress...")

        # 获取当前活动信息
        current_activity_info = await self.screenshot_tool.get_current_activity()

        # 获取当前屏幕描述信息
        screenshot_file_info, perception_infos = await self.get_screen_description()
        screen_info = ScreenInfo(screenshot_file_info, perception_infos, current_activity_info)

        logger.bind(log_tag="fairy_sys").info("[Get Screenshot] and [Perception Information] Task completed.")
        await self.publish("app_channel", EventMessage(EventType.ScreenPerception_DONE, screen_info))

    async def get_screen_description(self):
        # 获取屏幕截图信息和UI层次结构XML(AccessibilityTree)
        screenshot_file_info, ui_hierarchy_xml = await self.screenshot_tool.get_screen()
        screenshot_file_info.compress_image_to_jpeg() # 压缩图片

        # 获取当前输入法激活状态
        get_keyboard_activation_status = await self.screenshot_tool.get_keyboard_activation_status()

        if self.screen_perception_type == ScreenPerceptionType.SSIP:
            # Use SSIP
            ssip = ScreenStructuredInfoPerception(self.visual_prompt_model_config, self.text_summarization_model_config)
            screenshot_file_info, perception_infos = await ssip.get_perception_infos(screenshot_file_info, ui_hierarchy_xml)
        elif self.screen_perception_type == ScreenPerceptionType.FVP:
            # Use FVP
            if FineGrainedVisualPerceptor is None:
                raise ImportError("FineGrainedVisualPerceptor requires additional dependencies. Please install them.")
            fvp = FineGrainedVisualPerceptor(self.visual_prompt_model_config)
            screenshot_file_info, perception_infos = fvp.get_perception_infos(screenshot_file_info)
        else:
            raise RuntimeError("Unsupported screen perception type: {}".format(self.screen_perception_type))

        perception_infos.keyboard_status = get_keyboard_activation_status[1] # 设置键盘激活状态
        return screenshot_file_info, perception_infos
