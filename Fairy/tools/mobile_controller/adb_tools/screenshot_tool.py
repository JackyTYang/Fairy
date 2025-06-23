import asyncio
import re
import subprocess

from loguru import logger

from Fairy.entity.info_entity import ScreenFileInfo, ActivityInfo
from Fairy.tools.mobile_controller.entity import MobileScreenshot
from Fairy.utils.task_executor import TaskExecutor


class AdbMobileScreenshot(MobileScreenshot):
    def __init__(self, config):
        self.adb_path = config.get_adb_path()
        # Path of desktop local temporary storage
        self.screenshot_temp_path = config.get_screenshot_temp_path()
        # Path of mobile phone screenshot
        self.screenshot_phone_path = config.screenshot_phone_path
        self.screenshot_filename = config.screenshot_filename


    async def get_screen(self):

        screenshot_file_info = ScreenFileInfo(self.screenshot_temp_path, self.screenshot_filename, 'png')

        # Path of mobile phone screenshot
        screenshot_file = f"{self.screenshot_phone_path}/{screenshot_file_info.get_screenshot_filename()}"
        commands = [
            f"{self.adb_path} shell screencap -p {screenshot_file}",
            f"{self.adb_path} pull {screenshot_file} {screenshot_file_info.file_path}",
            f"{self.adb_path} shell rm {screenshot_file}"]

        async def _get_screen():
            logger.bind(log_tag="fairy_sys").info("[Get Screenshot] TASK in progress...")
            for command in commands:
                result = subprocess.run(command, capture_output=True, text=True, shell=True)
                if result.returncode != 0:
                    raise RuntimeError(f"[ADB] Error occurred while getting screenshot: {result.stderr}")
                await asyncio.sleep(1)

        await TaskExecutor("Get_Screenshot", None).run(_get_screen)

        logger.bind(log_tag="fairy_sys").info("[Get Screenshot] TASK completed.")
        return screenshot_file_info, None

    async def get_current_activity(self):
        async def _get_current_activity_info():
            logger.bind(log_tag="fairy_sys").info("[Get Current Activity] TASK in progress...")
            result = subprocess.run(["powershell", "-Command", f"{self.adb_path} shell dumpsys window | findstr 'mCurrentFocus'"], capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                pattern = r"mCurrentFocus=Window\{([a-f0-9]+) u(\d+) ([^/]+)/(.*)\}"
                current_activity_info = re.match(pattern, result.stdout)
                if current_activity_info:
                    return current_activity_info.groups()
                else:
                    raise RuntimeError(f"[ADB] Error occurred while getting current activity: {result.stderr}")
            else:
                raise RuntimeError(f"[ADB] Error occurred while getting current activity, Abnormal Exit: {result.returncode}")

        result = await TaskExecutor("Get_Screenshot", None).run(_get_current_activity_info)
        return ActivityInfo(package_name=result[2], activity=result[3], user_id=result[1], window_id=result[0])

    async def get_keyboard_activation_status(self):
        logger.bind(log_tag="fairy_sys").info("[Get Keyboard Activation Status] TASK in progress...")
        result = subprocess.run(["powershell", "-Command", f"{self.adb_path} shell dumpsys input_method | findstr 'mCurMethodId mInputShown'"], capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            matches = re.findall(r'mCurMethodId=(\S+)|mInputShown=(\w+)', result.stdout.lstrip())
            if len(matches) == 2:
                keyboard_activation_status = [match[0] or match[1] for match in matches]
            else:
                raise RuntimeError(f"[ADB] Error occurred while getting current keyboard activation status, Regular Expression Parsing Failed: {result.stderr.lstrip()}")
        else:
            raise RuntimeError(f"[ADB] Error occurred while getting current keyboard activation status, Abnormal Exit: {result.returncode}")
        return keyboard_activation_status