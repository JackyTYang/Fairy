import asyncio
import re

from loguru import logger

from Fairy.info_entity import ScreenFileInfo, ActivityInfo
import uiautomator2 as u2

from Fairy.tools.mobile_controller.entity import MobileScreenshot


class UiAutomatorMobileScreenshot(MobileScreenshot):
    def __init__(self, config):
        self.screenshot_temp_path = config.get_screenshot_temp_path()
        self.screenshot_filename = config.screenshot_filename

        self.dev = u2.connect(config.device)


    async def get_screen(self):
        logger.bind(log_tag="fairy_sys").info("[Get Screenshot & UI Hierarchy] TASK in progress...")

        await asyncio.sleep(5) # 避免速度过快导致屏幕内容没有完成加载

        screenshot_file_info = ScreenFileInfo(self.screenshot_temp_path, self.screenshot_filename, 'png')
        # get screenshot
        self.dev.screenshot(screenshot_file_info.get_screenshot_fullpath())
        # get ui hierarchy
        ui_hierarchy_xml = self.dev.dump_hierarchy()

        logger.bind(log_tag="fairy_sys").info("[Get Screenshot & UI Hierarchy] TASK completed.")
        return screenshot_file_info, ui_hierarchy_xml

    async def get_current_activity(self):
        logger.bind(log_tag="fairy_sys").info("[Get Current Activity] TASK in progress...")

        output, exit_code = self.dev.shell("dumpsys window | grep 'mCurrentFocus'", timeout=60)

        pattern = r"mCurrentFocus=Window\{([a-f0-9]+) u(\d+) ([^/]+)/(.*)\}"
        current_activity_info = re.match(pattern, output.lstrip())
        if exit_code == 0:
            if current_activity_info:
                result = current_activity_info.groups()
            else:
                raise RuntimeError(f"Error occurred while getting current activity, Regular Expression Parsing Failed: {output.lstrip()}")
        else:
            raise RuntimeError(f"Error occurred while getting current activity, Abnormal Exit: {exit_code}")
        return ActivityInfo(package_name=result[2], activity=result[3], user_id=result[1], window_id=result[0])