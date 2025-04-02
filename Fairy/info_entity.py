import os
from datetime import datetime
from typing import List, Dict

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

    def compress_image_to_jpeg(self, quality=50):
        with PILImage.open(self.get_screenshot_fullpath()) as img:
            img = img.convert('RGB')
            self.file_type = 'jpeg'
            img.save(self.get_screenshot_fullpath(), 'JPEG', quality=quality)


class ScreenPerceptionInfo:
    def __init__(self, screenshot_file_info: ScreenFileInfo, perception_infos):
        self.screenshot_file_info = screenshot_file_info
        self.perception_infos = perception_infos

    def __str__(self):
        return f"ScreenPerceptionInfo: {self.perception_infos}"

class PlanInfo:
    def __init__(self, plan_thought, overall_plan, current_sub_goal, user_interaction_type):
        self.plan_thought = plan_thought
        self.overall_plan = overall_plan
        self.current_sub_goal = current_sub_goal
        self.user_interaction_type = user_interaction_type

    def __str__(self):
        return (f"\n -------------PlanInfo-------------"
                f"\n - Plan Thought:{self.plan_thought}"
                f"\n - Plan: {self.overall_plan}"
                f"\n - Current Sub Goal: {self.current_sub_goal}"
                f"\n - User Interaction Type: {self.user_interaction_type}"
                f"\n -----------PlanInfo END-----------")

class ActionInfo:
    def __init__(self, action_thought, actions:List[Dict[str, AtomicActionType | dict]], action_expectation):
        self.action_thought = action_thought
        self.actions = actions
        self.action_expectation = action_expectation

    def __str__(self):
        return (f"\n -------------ActionInfo-------------"
                f"\n - Action Thought:{self.action_thought}"
                f"\n - Actions: {self.actions}"
                f"\n - Action Expectation: {self.action_expectation}"
                f"\n -----------ActionInfo END-----------")

class ProgressInfo:
    def __init__(self, action_result, error_potential_causes, progress_status):
        self.action_result = action_result
        self.error_potential_causes = error_potential_causes
        self.progress_status = progress_status

    def __str__(self):
        return (f"\n -------------ProgressInfo-------------"
                f"\n - Action Result: {self.action_result}"
                f"\n - Error Potential Causes: {self.error_potential_causes}"
                f"\n - Progress Status: {self.progress_status}"
                f"\n -----------ProgressInfo END-----------")

class UserInteractionInfo:
    def __init__(self, interaction_status, interaction_thought, action_instruction, response):
        self.interaction_status = interaction_status
        self.interaction_thought = interaction_thought
        self.action_instruction = action_instruction
        self.response = response

    def __str__(self):
        return (f"\n -------------UserInteractionInfo-------------"
                f"\n - Interaction Status: {self.interaction_status}"
                f"\n - Interaction Thought: {self.interaction_thought}"
                f"\n - Action Instruction: {self.action_instruction}"
                f"\n - Response: {self.response}"
                f"\n -----------UserInteractionInfo END-----------")