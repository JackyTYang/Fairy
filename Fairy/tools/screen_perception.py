import asyncio
import subprocess
from datetime import datetime

from .FVP.perceptor import FineGrainedVisualPerceptor
from .entity import ScreenFileInfo
from ..utils.task_executor import TaskExecutor


class ScreenPerception:
    def __init__(self, config):
        self.adb_path = config.adb_path
        # Path of desktop local temporary storage
        self.screenshot_temp_path = config.screenshot_temp_path
        # Path of mobile phone screenshot
        self.screenshot_filepath = config.screenshot_filepath
        self.screenshot_filename = config.screenshot_filename

    async def get_screen(self):

        screenshot_file_info = ScreenFileInfo(self.screenshot_temp_path, self.screenshot_filename, 'png')

        # Path of mobile phone screenshot
        screenshot_file = f"{self.screenshot_filepath}/{screenshot_file_info.get_screenshot_filename()}"
        commands = [
            f"{self.adb_path} shell screencap -p {screenshot_file}",
            f"{self.adb_path} pull {screenshot_file} {screenshot_file_info.file_path}",
            f"{self.adb_path} shell rm {screenshot_file}"]

        async def _get_screen():
            for command in commands:
                result = subprocess.run(command, capture_output=True, text=True, shell=True)
                if result.returncode != 0:
                    raise RuntimeError(f"Error occurred while obtaining screenshot: {result.stderr}")
                await asyncio.sleep(1)

        await TaskExecutor("Get_Screenshot", None).run(_get_screen)
        return screenshot_file_info

    async def get_screen_description(self):
        screenshot_file_info = await self.get_screen()
        # Use FVP
        fvp = FineGrainedVisualPerceptor()
        return screenshot_file_info, fvp.get_perception_infos(screenshot_file_info)
