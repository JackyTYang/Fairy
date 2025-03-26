import json
import re

from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.info_entity import PlanInfo, ProgressInfo, ScreenPerceptionInfo, ActionInfo
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventType, EventStatus, CallType, MemoryType


class UserInteractorAgent(Agent):
    def __init__(self, runtime, model_client) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to interact with the user. Think as if you are a human user operating the phone.",
            type="SystemMessage")]
        super().__init__(runtime, "UserInteractorAgent", model_client, system_messages)
        self.init_user_interactor = False

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.Plan and msg.status == EventStatus.DONE)
    async def on_user_interactor_init(self, message: EventMessage, message_context):
        logger.info("[UserInteract(First Run)] TASK in progress...")

        self.init_user_interactor = True
        instruction = message.event_content
        # 从ShortTimeMemoryManager获取CurrentScreenPerception
        memory = await self.call("ShortTimeMemoryManager", CallMessage(CallType.Memory_GET, [MemoryType.ScreenPerception]))
        memory = await memory
        # 构建Prompt
        plan_event_content, reflection_event_content = await self.request_llm(
            self.build_init_prompt(instruction,
                                   message.event_content,  # PlanInfo
                                   memory[MemoryType.ActionResult][-1],  # ProgressInfo
                                   memory[MemoryType.KeyInfo],  # KeyInfoList
                                   memory[MemoryType.ScreenPerception][-1]),
            [
                memory[MemoryType.ScreenPerception][-1].screenshot_file_info.get_screenshot_Image_file(), # CurrentScreenImageFile
            ]
        )
        # 发布Plan事件
        await self.publish("app_channel", EventMessage(EventType.Plan, EventStatus.DONE, plan_event_content))
        logger.info("[UserInteract(First Run)] TASK completed.")
        self.init_user_interactor = False

    @staticmethod
    def build_init_prompt(instruction,
                          plan_info: PlanInfo,
                          progress_info: ProgressInfo,
                          key_infos: list,
                          current_screen_perception_info: ScreenPerceptionInfo) -> str:
        prompt = f"The planner has just discovered that to execute the current sub-goal, it needs to interact with the user as necessary. This is the user guide, overall plan, sub-goals, and historical progress:"\
                 f"- Instruction: {instruction}\n"\
                 f"- Overall Plan: {plan_info.overall_plan}\n" \
                 f"- Sub-goal: {plan_info.current_sub_goal}\n" \
                 f"- History Progress Status: {progress_info.progress_status if progress_info is not None else 'No progress yet.'}\n" \

        prompt += f"---\n"\
                  f"Please follow the steps below to perform the action:\n" \
                  f"1. Carefully examine the information provided above and the current screen shot to determine which of the following types of interaction with the user this is:\n" \
                  f"- A: Confirmation of Sensitive or Dangerous Operations. The sub-goal contains sensitive or dangerous operations that require explanation of the situation to the user and the user's consent to proceed with the action. e.g.completely deleting a file requires confirmation from the user;\n" \
                  f"- B: Require the user to make choices about different options. There are multiple optional options that meet the user's instruction, and the user is required to make a choice before proceeding with the action. e.g.there are multiple search results that meet the user's instruction that require further decision making by the user;\n" \
                  f"- C: The user is asked for further clarification of the request. The instructions given by the user are too vague and require further clarification from the user. e.g.the user requests a phone call but does not specify a contact person, requiring further clarification from the user.\n"

        prompt += f"2. For Interaction Types A and C, it is possible to interact directly with the user; however, for Interaction Type B, please check whether further information needs to be collected for the user's decision-making. Please ensure that the possible options have been fully investigated (where there are more than 10 options, only 10 options need be provided)."\
                  "Please determine which of the following types of actions need to be performed at this time:\n"\
                  "- 0: More information needs to be gathered to interact with the user;\n"\
                  "- 1: Need not to gather more information to interact with the user immediately;\n"\

        prompt += f"---\n"\
                  f"Please provide a JSON with 5 keys, which are interpreted as follows:\n"\
                  f"- interaction_type: Please use A, B, C to indicate"\
                  f"- action_type: Please use 0, 1 to indicate\n" \
                  f"- interaction_thought: please explain Explain in detail your reasons for choosing the Interaction Type and Action Type.\n"\
                  f"- action_instruction: If the Action Type is 1, please write 'none'; If the Action Type is 0, please provide instructions on information collection;\n" \
                  f"- user_prompts: If the Action Type is 1, fill in prompts that will help the user to make a response or choice;  If the Action Type is 0, please write 'None'.\n"\
                  f"Make sure this JSON can be loaded correctly by json.load().\n" \
                  f"\n"
        return prompt

    def parse_response(self, response: str) -> (PlanInfo, ProgressInfo):
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        response_jsonobject = json.loads(response)

        plan_info = PlanInfo(response_jsonobject['plan_thought'], response_jsonobject['overall_plan'], response_jsonobject['current_sub_goal'])
        if 'action_result' in response_jsonobject:
            progress_info = ProgressInfo(response_jsonobject['action_result'], response_jsonobject['error_potential_causes'],
                     response_jsonobject['progress_status'])
        else:
            progress_info = None
        return plan_info, progress_info
