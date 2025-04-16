from loguru import logger

from Citlali.core.type import ListenerType
from Citlali.core.worker import Worker, listener
from Fairy.config.fairy_config import MobileControllerType, ScreenPerceptionType
from Fairy.tools.mobile_controller.adb_tools.screenshot_tool import AdbMobileScreenshot
from Fairy.tools.mobile_controller.ui_automator_tools.screenshot_tool import UiAutomatorMobileScreenshot
from Fairy.info_entity import ScreenInfo
from Fairy.message_entity import EventMessage
from Fairy.tools.screen_perceptor.assm.perceptor import AdaptiveSemanticScreenModeling
from Fairy.tools.screen_perceptor.fvp.perceptor import FineGrainedVisualPerceptor
from Fairy.type import EventStatus, EventType


class ScreenPerceptor(Worker):
    def __init__(self, runtime, config):
        super().__init__(runtime, "ScreenPerceptor", "ScreenPerceptor")

        self.screenshot_getter_type = config.screenshot_getter_type
        if self.screenshot_getter_type == MobileControllerType.ADB:
            self.screenshot_tool = AdbMobileScreenshot(config)
        elif self.screenshot_getter_type == MobileControllerType.UIAutomator:
            self.screenshot_tool = UiAutomatorMobileScreenshot(config)

        self.screen_perception_type = config.screen_perception_type
        if self.screen_perception_type == ScreenPerceptionType.ASSM and self.screenshot_getter_type == MobileControllerType.ADB:
            raise ValueError("ASSM requires uiautomator screenshot tool, but adb is used.")

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.ActionExecution and message.status == EventStatus.DONE)
    async def on_screen_percept(self, message: EventMessage, message_context):
        await self._on_screen_percept(message, message_context)

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.Task and message.status == EventStatus.CREATED)
    async def on_first_screen_percept(self, message: EventMessage, message_context):
        await self._on_screen_percept(message, message_context)

    async def _on_screen_percept(self, message: EventMessage, message_context):
        logger.bind(log_tag="fairy_sys").info("[Get Screenshot] and [Perception Information] Task in progress...")
        screenshot_file_info, perception_infos = await self.get_screen_description()
        logger.bind(log_tag="fairy_sys").info("[Get Screenshot] and [Perception Information] Task completed.")
        await self.publish("app_channel", EventMessage(EventType.ScreenPerception, EventStatus.DONE, ScreenInfo(screenshot_file_info, perception_infos)))

    async def get_screen_description(self):
        screenshot_file_info, ui_hierarchy_xml = await self.screenshot_tool.get_screen()
        screenshot_file_info.compress_image_to_jpeg()

        if self.screen_perception_type == ScreenPerceptionType.FVP:
            # Use FVP
            fvp = FineGrainedVisualPerceptor()
            return fvp.get_perception_infos(screenshot_file_info)
        elif self.screen_perception_type == ScreenPerceptionType.ASSM:
            # Use ASSM
            assm = AdaptiveSemanticScreenModeling()
            return assm.get_perception_infos(screenshot_file_info, ui_hierarchy_xml)

