from datetime import datetime
from typing import List, Dict

from Citlali.utils.image import Image
from PIL import Image as PILImage
from Fairy.tools.mobile_controller.action_type import AtomicActionType


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

class ActivityInfo:
    def __init__(self, package_name, activity, user_id, window_id):
        self.package_name = package_name
        self.activity = activity
        self.user_id = user_id
        self.window_id = window_id

class ScreenInfo:
    def __init__(self, screenshot_file_info: ScreenFileInfo, perception_infos, current_activity_info: ActivityInfo):
        self.current_activity_info = current_activity_info
        self.screenshot_file_info = screenshot_file_info
        self.perception_infos = perception_infos

    def __str__(self):
        return (f"\n -------------ScreenInfo-------------"
                f"\n - Package Name: {self.current_activity_info.package_name}"
                f"\n - Activity: {self.current_activity_info.activity}"
                f"\n - Perception Info: {self.perception_infos}"
                f"\n -----------ScreenInfo END-----------")

class PlanInfo:
    def __init__(self, plan_thought, overall_plan, current_sub_goal, user_interaction_type, user_interaction_thought):
        self.plan_thought = plan_thought
        self.overall_plan = overall_plan
        self.current_sub_goal = current_sub_goal
        self.user_interaction_type = user_interaction_type
        self.user_interaction_thought = user_interaction_thought

    def __str__(self):
        return (f"\n -------------PlanInfo-------------"
                f"\n - Plan Thought:{self.plan_thought}"
                f"\n - Plan: {self.overall_plan}"
                f"\n - Current Sub Goal: {self.current_sub_goal}"
                f"\n - User Interaction Type: {self.user_interaction_type}"
                f"\n - User Interaction Thought: {self.user_interaction_thought}"
                f"\n -----------PlanInfo END-----------")

class GlobalPlanInfo:
    def __init__(self, global_plan_thought, global_plan, current_sub_task, ins_language, delivered_key_info=None, previously_execution_result=None):
        self.global_plan_thought = global_plan_thought
        self.global_plan = global_plan
        self.current_sub_task = current_sub_task
        self.ins_language = ins_language
        self.delivered_key_info = delivered_key_info
        self.previously_execution_result = previously_execution_result

    def __str__(self):
        return (f"\n -------------GlobalPlanInfo-------------"
                f"\n - Previous Execution Result:{'No Previous Execution' if self.previously_execution_result is None else self.previously_execution_result}"
                f"\n - Global Plan Thought:{self.global_plan_thought}"
                f"\n - Global Plan: {self.global_plan}"
                f"\n - Current Sub Task: {self.current_sub_task}"
                f"\n - Ins Language: {self.ins_language}"
                f"\n - Delivered Key Info: {self.delivered_key_info}"
                f"\n -----------GlobalPlanInfo END-----------")

class ActionInfo:
    def __init__(self, action_thought, actions:List[Dict[str, AtomicActionType | dict]], action_expectation, user_interaction_thought: str):
        self.action_thought = action_thought
        self.actions = actions
        self.action_expectation = action_expectation
        self.user_interaction_thought = user_interaction_thought

    def __str__(self):
        return (f"\n -------------ActionInfo-------------"
                f"\n - Action Thought:{self.action_thought}"
                f"\n - Actions: {self.actions}"
                f"\n - Action Expectation: {self.action_expectation}"
                f"\n - User Interaction Thought: {self.user_interaction_thought}"
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

class InstructionInfo:
    def __init__(self, ori, language, key_info_request):
        self.ori = ori
        self.language = language
        self.key_info_request = key_info_request
        self.updated = []

    def __str__(self):
        return (f"\n -------------InstructionInfo-------------"
                f"\n - Original Instruction : {self.ori}"
                f"\n - Instruction Language: {self.language}"
                f"\n - Key Info Request: {self.key_info_request}"
                f"\n - User Update Instructions: {self.updated}"
                f"\n -----------InstructionInfo END-----------")

    def get_instruction(self):
        return (self.ori + (f" | Instructions added after user interaction: {','.join(self.updated)}" if len(self.updated) > 0 else "")) if self.ori is not None else None