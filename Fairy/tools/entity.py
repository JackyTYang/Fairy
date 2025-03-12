import os
from datetime import datetime


class ScreenFileInfo:
    def __init__(self,file_path, file_name, file_type):
        self.file_path = file_path
        self.file_name = file_name
        self.file_type = file_type
        self.file_build_timestamp = int(datetime.now().timestamp())

    def get_screenshot_filename(self, extra_filename: str = None, no_type: bool = False) -> str:
        return (f"{self.file_name}_"
                f"{str(self.file_build_timestamp)}{'' if extra_filename is None else extra_filename}"
                f"{''if no_type else f'.{self.file_type}'}")

    def get_screenshot_file(self, extra_filename: str = None):
        return f"{self.file_path}/{self.get_screenshot_filename(extra_filename)}"
