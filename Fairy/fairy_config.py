class Config:
    def __init__(self, adb_path, temp_path=None,
                 screenshot_phone_path=None,
                 screenshot_filename=None,
                 action_executor_type=None,
                 screenshot_getter_type=None,
                 screen_perception_type=None):
        self.adb_path = adb_path
        self.device = None

        self.temp_path = "tmp" if temp_path is None else temp_path

        self.screenshot_temp_path = self.temp_path + "/screenshot"
        self.screenshot_phone_path = "/sdcard" if screenshot_phone_path is None else screenshot_phone_path

        self.screenshot_filename = "screenshot" if screenshot_filename is None else screenshot_filename

        self.action_executor_type = "uiautomator" if action_executor_type is None else action_executor_type # default action executor type
        self.screenshot_getter_type = "uiautomator" if screenshot_getter_type is None else screenshot_getter_type  # default screenshot getter type
        self.screen_perception_type = "assm" if screen_perception_type is None else screen_perception_type # default screen_perception_type
    def get_adb_path(self):
        return (self.adb_path + f" -s {self.device}") if self.device is not None else self.adb_path