import json
import re

from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.info_entity import PlanInfo, ProgressInfo, ScreenPerceptionInfo, ActionInfo, UserInteractionInfo
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventType, EventStatus, CallType, MemoryType


class AppPlannerAgent(Agent):
    def __init__(self, runtime, model_client) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to verify whether the last action produced the expected behavior, to keep track of the progress and devise high-level plans to achieve the user's requests. Think as if you are a human user operating the phone.",
            type="SystemMessage")]
        super().__init__(runtime, "AppPlannerAgent", model_client, system_messages)
        self.init_plan = False

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.Plan and msg.status == EventStatus.CREATED)
    async def on_plan_init(self, message: EventMessage, message_context):
        logger.info("[Plan(First Run)] TASK in progress...")

        self.init_plan = True
        instruction = message.event_content
        # 从ShortTimeMemoryManager获取CurrentScreenPerception
        memory = await self.call("ShortTimeMemoryManager", CallMessage(CallType.Memory_GET, [MemoryType.ScreenPerception]))
        memory = await memory
        # 构建Prompt
        plan_event_content, reflection_event_content = await self.request_llm(
            self.build_init_prompt(instruction),
            [
                memory[MemoryType.ScreenPerception][-1].screenshot_file_info.get_screenshot_Image_file(), # CurrentScreenImageFile
            ]
        )
        # 发布Plan事件
        await self.publish("app_channel", EventMessage(EventType.Plan, EventStatus.DONE, plan_event_content))
        logger.info("[Plan(First Run)] TASK completed.")
        self.init_plan = False

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: (msg.event == EventType.ScreenPerception or msg.event == EventType.UserInteraction) and msg.status == EventStatus.DONE)
    async def on_plan_next(self, message: EventMessage, message_context):
        if self.init_plan:
            return

        logger.debug("[Plan] TASK in progress...")

        # 从ShortTimeMemoryManager获取Instruction, CurrentScreenPerception, Plan
        memory = await self.call("ShortTimeMemoryManager", CallMessage(CallType.Memory_GET, [MemoryType.Instruction, MemoryType.Plan, MemoryType.Action, MemoryType.ActionResult, MemoryType.ScreenPerception]))
        memory = await memory
        # 构建Prompt
        plan_event_content, reflection_event_content = await self.request_llm(
            self.build_prompt(
                memory[MemoryType.Instruction], # Instruction
                memory[MemoryType.Plan][-1], # PlanInfo
                memory[MemoryType.Action][-1],  # ActionInfo
                # ProgressInfoList can be empty if this is the first reflection
                memory[MemoryType.ActionResult][-1] if len(memory[MemoryType.ActionResult]) > 0 else None, # ProgressInfo
                memory[MemoryType.ScreenPerception][-2], # PreviousScreenPerceptionInfo
                message.event_content if message.event == EventType.ScreenPerception else memory[MemoryType.ScreenPerception][-1] # CurrentScreenPerceptionInfo
            ),
            [
                memory[MemoryType.ScreenPerception][-2].screenshot_file_info.get_screenshot_Image_file(), # PreviousScreenImageFile
                message.event_content.screenshot_file_info.get_screenshot_Image_file() # CurrentScreenImageFile
            ]
        )

        # 发布Plan事件
        await self.publish("app_channel", EventMessage(EventType.Reflection, EventStatus.DONE, reflection_event_content))

        if not self.is_finished_action(reflection_event_content, memory[MemoryType.Action][-1]):
            await self.publish("app_channel", EventMessage(EventType.Plan, EventStatus.DONE, plan_event_content))
        logger.info("[Plan] TASK completed.")


    @staticmethod
    def is_finished_action(progress_info: ProgressInfo, action_info: ActionInfo) -> bool:
        if progress_info.action_result == "A" and len(action_info.actions) > 0 and action_info.actions[0]['name'] == "Finish":
            logger.info("All requirements in the user's Instruction have been completed.")
            return True
        return False

    @staticmethod
    def build_init_prompt(instruction) -> str:
        prompt = f"- Instruction: {instruction}\n"\
                 f"\n"

        prompt += f"---\n"\
                  f"Think step by step and make an high-level plan to achieve the user's instruction. If the request is complex, break it down into sub-goals. If the request involves exploration, include concrete sub-goals to quantify the investigation steps. The screenshot displays the starting state of the phone.\n"\
                  f"\n"

        prompt += f"---\n"\
                  f"Please provide a JSON with 4 keys, which are interpreted as follows:\n"\
                  f"- plan_thought: A detailed explanation of your rationale for the plan and subgoals.\n"\
                  f"- overall_plan: Consisting of multiple sub-goals, which need to be prefixed with a numerical number, e.g.'1.first sub-goal;2.second sub-goal;...'\n"\
                  f"- current_sub_goal: The first subgoal you should work on.\n" \
                  f"- user_interaction_type: Please use 0 to indicate." \
                  f"Make sure this JSON can be loaded correctly by json.load().\n" \
                  f"\n"
        return prompt

    @staticmethod
    def build_prompt(instruction,
                     plan_info: PlanInfo,
                     action_info: ActionInfo,
                     progress_info: ProgressInfo,
                     previous_screen_perception_info: ScreenPerceptionInfo,
                     current_screen_perception_info: ScreenPerceptionInfo) -> str:
        prompt = f"---\n"\
                 f"The Executor Agent has just finished executing according to your previous plan, which is the sub-goal, action, and expected results of this execution:\n"\
                 f"- Sub-goal: {plan_info.current_sub_goal}\n"\
                 f"- Action(s): {action_info.actions}\n"\
                 f"- Action Expectation: {action_info.action_expectation}\n"\
                 f"\n"

        prompt += f"---\n"
        prompt += previous_screen_perception_info.perception_infos.get_screen_info_note_prompt("The two attached images are two screenshots of your phone before and after your last action to reveal the change in status") # Call this function to supplement the prompt "Size of the Image and Additional Information".
        prompt += f"\n"

        prompt += previous_screen_perception_info.perception_infos.get_screen_info_prompt("before the Action") # Call this function to get the content of the prompt "Screen Perception Information and Keyboard Status".
        prompt += current_screen_perception_info.perception_infos.get_screen_info_prompt("after the Action") # Call this function to get the content of the prompt "Screen Perception Information and Keyboard Status".

        prompt += f"---\n"\
                  f"- Instruction: {instruction}\n"\
                  f"- Overall Plan: {plan_info.overall_plan}\n"\
                  f"- History Progress Status: {progress_info.progress_status if progress_info is not None else 'No progress yet.'}\n" \
                  f"\n" \
                  f"Please follow the steps below to perform the action:\n" \
                  f"1. Carefully examine the screenshots and screen information before and after the action provided above to determine which of the following resulted from this action:\n" \
                  f"- A: Successful, with results meeting expectations and fully accomplishing the sub-goal;\n" \
                  f"- B: Partial Successful, where the result was as expected but did not fully accomplish the sub-goal. For example, all options should be selected, but currently only some options are selected;\n" \
                  f"- C: Failure, the result is incorrect and an attempt to fall back to the previous state is required;\n" \
                  f"- D: Failure, the action was executed without producing any change.\n" \
                  f"2. If the result is A, then: update the 'History Progress Status'; mark the task as completed in the 'Overall Plan'; and determine the next 'Sub-goal' to be executed based on the plan.\n" \
                  f"3. If the result is B, then: update the 'History Progress Status'; outline the 'Sub-goal' that should be continued next.\n" \
                  f"4. If the result is C or D, then: try to explain the 'Error Potential Causes' of the failure; think step-by-step about whether the 'Overall Plan' needs to be revised to address the error; determine the next 'Sub-goal' to be executed based on the plan.\n" \
                  f"5. In the following cases where user interaction is required, determine whether user interaction is required next, and select 0 if no user interaction is required:\n" \
                  f"- 1: Confirmation of sensitive or dangerous action. The sub-target contains sensitive or dangerous action that the user has not requested very explicitly in the user instruction, e.g., file deletion when the user has not instructed file deletion.\n" \
                  f"- 2: Confirmation of irreversible action. The action is irreversible regardless of whether the user has given instruction, e.g., a file deletion that requires the user to reconfirm the action before the file is irreversibly deleted. MAKE SURE that the action is indeed irreversible.\n" \
                  f"- 3: Choice of different options. Multiple options are presented that satisfy the user's instructions, e.g., there are multiple search results that meet the user's instruction that require further decision-making by the user.\n" \
                  f"- 4: Further clarification of instruction. The instruction given by the user are vague, e.g., the user asks to make a phone call but does not specify a contact person.\n" \
                  f"\n"

        prompt += f"NOTE: Moving to the recycle bin is not a irreversible deletion!\n" \
                  f"\n"

        prompt += f"---\n"\
                  f"Please provide a JSON with 7 keys, which are interpreted as follows:\n"\
                  f"- action_result: Please use A, B, C, and D to indicate.\n"\
                  f"- error_potential_causes: If the action_result is A or B, please fill in 'None' here. If the action_result is C or D, please describe in detail the error and the potential cause of failure.\n"\
                  f"- progress_status: If the action_result is A or B, update the progress status. If the action_result is C or D, copy the previous progress status.\n"\
                  f"- plan_thought: Explain in detail your rationale for developing or modifying the plan and sub-goals.\n"\
                  f"- overall_plan: If you need to update the plan, provide the updated plan here. Otherwise keep the current plan and copy it here.\n"\
                  f"- current_sub_goal: The next subgoal. If all subgoals have been completed, write 'Completed'.\n"\
                  f"- user_interaction_type: Please use 0, 1, 2, 3, and 4 to indicate."\
                  f"Make sure this JSON can be loaded correctly by json.load().\n"\
                  f"\n"

        return prompt

    def parse_response(self, response: str) -> (PlanInfo, ProgressInfo):
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        response_jsonobject = json.loads(response)

        plan_info = PlanInfo(response_jsonobject['plan_thought'], response_jsonobject['overall_plan'], response_jsonobject['current_sub_goal'], response_jsonobject['user_interaction_type'])
        if 'action_result' in response_jsonobject:
            progress_info = ProgressInfo(response_jsonobject['action_result'], response_jsonobject['error_potential_causes'],
                     response_jsonobject['progress_status'])
        else:
            progress_info = None
        return plan_info, progress_info
