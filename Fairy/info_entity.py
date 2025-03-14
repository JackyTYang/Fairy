import os
from datetime import datetime

from Citlali.utils.image import Image
from PIL import Image as PILImage
from .tools.action_type import AtomicActionType


class ScreenFileInfo:
    def __init__(self,file_path, file_name, file_type):
        self.file_path = file_path
        self.file_name = file_name
        self.file_extra_name = None
        self.file_type = file_type
        self.file_build_timestamp = int(datetime.now().timestamp())

    def set_extra_name(self, extra_name):
        self.file_extra_name = extra_name

    def get_screenshot_filename(self, no_type: bool = False) -> str:
        return (f"{self.file_name}_"
                f"{str(self.file_build_timestamp)}{'' if self.file_extra_name is None else self.file_extra_name}"
                f"{''if no_type else f'.{self.file_type}'}")

    def get_screenshot_fullpath(self):
        return f"{self.file_path}/{self.get_screenshot_filename()}"

    def get_screenshot_Image_file(self):
        return Image(PILImage.open(self.get_screenshot_fullpath()))


class ScreenPerceptionInfo:
    def __init__(self, screenshot_file_info: ScreenFileInfo, perception_infos):
        self.screenshot_file_info = screenshot_file_info
        self.perception_infos = perception_infos

    def __str__(self):
        return f"ScreenPerceptionInfo: {self.perception_infos}"

class PlanInfo:
    def __init__(self, thought, plan, current_sub_goal):
        self.thought = thought
        self.plan = plan
        self.current_sub_goal = current_sub_goal

    def __str__(self):
        return (f"Thought:{self.thought} \n"
                f"Plan: {self.plan} \n"
                f"CurrentSubGoal: {self.current_sub_goal} \n")

class ActionInfo:
    def __init__(self, thought, action:AtomicActionType, expectation, args:dict):
        self.thought = thought
        self.action = action
        self.expectation = expectation
        self.args = args

    def __str__(self):
        return (f"Thought:{self.thought} \n"
                f"Action: {self.action} \n"
                f"Expectation: {self.expectation} \n"
                f"Args: {self.args} \n")

class ProgressInfo:
    def __init__(self, outcome, error_description, progress_status):
        self.outcome = outcome
        self.error_description = error_description
        self.progress_status = progress_status

    def __str__(self):
        return (f"Outcome: {self.outcome} \n"
                f"Error Description: {self.error_description} \n"
                f"Progress Status: {self.progress_status} \n")