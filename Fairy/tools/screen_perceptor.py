import asyncio
import subprocess

from loguru import logger

from Citlali.core.type import ListenerType
from Citlali.core.worker import Worker, listener
from .assm.perceptor import AdaptiveSemanticScreenModeling
from .fvp.perceptor import FineGrainedVisualPerceptor
from .adb_tools.screenshot_tool import AdbMobileScreenshot
from .ui_automator_tools.screenshot_tool import UiAutomatorMobileScreenshot
from ..info_entity import ScreenFileInfo, ScreenPerceptionInfo
from Fairy.message_entity import EventMessage
from Fairy.type import EventStatus, EventType
from ..utils.task_executor import TaskExecutor


class ScreenPerceptor(Worker):
    def __init__(self, runtime, config):
        super().__init__(runtime, "ScreenPerceptor", "ScreenPerceptor")

        self.screenshot_getter_type = config.screenshot_getter_type
        if self.screenshot_getter_type == "adb":
            self.screenshot_tool = AdbMobileScreenshot(config)
        elif self.screenshot_getter_type == "uiautomator":
            self.screenshot_tool = UiAutomatorMobileScreenshot(config)

        self.screen_perception_type = config.screen_perception_type
        if self.screen_perception_type == "assm" and self.screenshot_getter_type == "adb":
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
        logger.info("[Get Screenshot] and [Perception Information] Task in progress...")
        screenshot_file_info, perception_infos = await self.get_screen_description()
        logger.info("[Get Screenshot] and [Perception Information] Task completed.")
        await self.publish("app_channel", EventMessage(EventType.ScreenPerception, EventStatus.DONE, ScreenPerceptionInfo(screenshot_file_info, perception_infos)))

    async def get_screen_description(self):
        screenshot_file_info, ui_hierarchy_xml = await self.screenshot_tool.get_screen()
        screenshot_file_info.compress_image_to_jpeg()

        if self.screen_perception_type == "fvp":
            # Use FVP
            fvp = FineGrainedVisualPerceptor()
            return fvp.get_perception_infos(screenshot_file_info)
        elif self.screen_perception_type == "assm":
            # Use ASSM
            assm = AdaptiveSemanticScreenModeling()
            return assm.get_perception_infos(screenshot_file_info, ui_hierarchy_xml)

