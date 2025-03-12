class Config:
    def __init__(self, adb_path, temp_path=None,
                 screenshot_filepath=None,
                 screenshot_filename=None):
        self.adb_path = adb_path

        self.temp_path = "./tmp" if temp_path is None else temp_path
        self.screenshot_temp_path = self.temp_path + "/screenshot"

        self.screenshot_filepath = "/sdcard" if screenshot_filepath is None else screenshot_filepath
        self.screenshot_filename = "screenshot" if screenshot_filename is None else screenshot_filename