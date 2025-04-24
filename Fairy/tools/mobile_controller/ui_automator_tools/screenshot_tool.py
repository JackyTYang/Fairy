import asyncio

from loguru import logger

from Fairy.info_entity import ScreenFileInfo
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