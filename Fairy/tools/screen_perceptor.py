import asyncio
import subprocess

from loguru import logger

from Citlali.core.type import ListenerType
from Citlali.core.worker import Worker, listener
from .FVP.perceptor import FineGrainedVisualPerceptor
from ..info_entity import ScreenFileInfo, ScreenPerceptionInfo
from Fairy.message_entity import EventMessage
from Fairy.type import EventStatus, EventType
from ..utils.task_executor import TaskExecutor


class ScreenPerceptor(Worker):
    def __init__(self, runtime, config):
        super().__init__(runtime, "ScreenPerceptor", "ScreenPerceptor")
        self.adb_path = config.get_adb_path()
        # Path of desktop local temporary storage
        self.screenshot_temp_path = config.screenshot_temp_path
        # Path of mobile phone screenshot
        self.screenshot_filepath = config.screenshot_filepath
        self.screenshot_filename = config.screenshot_filename

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

    async def get_screen(self):

        screenshot_file_info = ScreenFileInfo(self.screenshot_temp_path, self.screenshot_filename, 'png')

        # Path of mobile phone screenshot
        screenshot_file = f"{self.screenshot_filepath}/{screenshot_file_info.get_screenshot_filename()}"
        commands = [
            f"{self.adb_path} shell screencap -p {screenshot_file}",
            f"{self.adb_path} pull {screenshot_file} {screenshot_file_info.file_path}",
            f"{self.adb_path} shell rm {screenshot_file}"]

        async def _get_screen():
            logger.info("[Get Screenshot] TASK in progress...")
            for command in commands:
                result = subprocess.run(command, capture_output=True, text=True, shell=True)
                if result.returncode != 0:
                    raise RuntimeError(f"Error occurred while getting screenshot: {result.stderr}")
                await asyncio.sleep(1)

        await TaskExecutor("Get_Screenshot", None).run(_get_screen)

        logger.info("[Get Screenshot] TASK completed.")
        return screenshot_file_info

    async def get_screen_description(self):
        screenshot_file_info = await self.get_screen()
        screenshot_file_info.compress_image_to_jpeg()

        # Use FVP
        fvp = FineGrainedVisualPerceptor()
        return fvp.get_perception_infos(screenshot_file_info)
