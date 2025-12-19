"""
包装 Fairy 原生工具，使其使用单例设备连接
"""

from Fairy.tools.mobile_controller.ui_automator_tools.mobile_control_tool import UiAutomatorMobileController
from Fairy.tools.mobile_controller.ui_automator_tools.screen_capture_tool import UiAutomatorMobileScreenCapturer
from shared import DeviceManager


class SingletonUiAutomatorMobileController(UiAutomatorMobileController):
    """使用单例设备连接的 UiAutomatorMobileController"""

    def __init__(self, config):
        # 使用单例设备连接
        self.dev = DeviceManager.get_device(config.device)

        # 初始化日志模板（必需）
        from Fairy.entity.log_template import LogTemplate
        self.log_t = LogTemplate(self, "UiAutomatorMobileController")


class SingletonUiAutomatorMobileScreenCapturer(UiAutomatorMobileScreenCapturer):
    """使用单例设备连接的 UiAutomatorMobileScreenCapturer"""

    def __init__(self, config):
        self.screenshot_temp_path = config.get_screenshot_temp_path()
        self.screenshot_filename = config.screenshot_filename

        # 使用单例设备连接
        self.dev = DeviceManager.get_device(config.device)

        from Fairy.entity.log_template import LogTemplate
        self.log_t = LogTemplate(self, "UiAutomatorScreenCapturer")
