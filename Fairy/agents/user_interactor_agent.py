import json
import re
from typing import List

from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.info_entity import PlanInfo, ProgressInfo, ScreenPerceptionInfo, ActionInfo, UserInteractionInfo
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventType, EventStatus, CallType, MemoryType


class UserInteractorAgent(Agent):
    def __init__(self, runtime, model_client) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to interact with the user. Think as if you are a human user operating the phone.",
            type="SystemMessage")]
        super().__init__(runtime, "UserInteractorAgent", model_client, system_messages)

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.Plan and msg.status == EventStatus.DONE)
    async def on_user_interact(self, message: EventMessage, message_context):
        if message.event_content.user_interaction_type != 0:
            await self._on_user_interact(message, message_context)
        else:
            logger.info("[Interact With User] No user interaction required, skipped")

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.UserChat and msg.status == EventStatus.DONE)
    async def on_user_interact_reflect(self, message: EventMessage, message_context):
        await self._on_user_interact(message, message_context)

    async def _on_user_interact(self, message: EventMessage, message_context):
        logger.info("[Interact With User] TASK in progress...")

        # 从ShortTimeMemoryManager获取CurrentScreenPerception
        memory = await self.call("ShortTimeMemoryManager", CallMessage(CallType.Memory_GET, [MemoryType.Instruction,MemoryType.Plan,MemoryType.ActionResult,MemoryType.KeyInfo,MemoryType.UserInteraction,MemoryType.ScreenPerception]))
        memory = await memory
        # 构建Prompt
        interactor_event_content = await self.request_llm(
            self.build_init_prompt(memory[MemoryType.Instruction],
                                   memory[MemoryType.Plan][-1],  # PlanInfo
                                   memory[MemoryType.ActionResult][-1] if len(memory[MemoryType.ActionResult]) > 0 else None, # ProgressInfo
                                   memory[MemoryType.KeyInfo][-1] if len(memory[MemoryType.KeyInfo]) > 0 else None, # KeyInfoList
                                   memory[MemoryType.UserInteraction],  # KeyInfoList
                                   memory[MemoryType.ScreenPerception][-1]),
            [
                memory[MemoryType.ScreenPerception][-1].screenshot_file_info.get_screenshot_Image_file(), # CurrentScreenImageFile
            ]
        )

        if interactor_event_content.interaction_status == "B":
            await self.publish("app_channel", EventMessage(EventType.UserChat, EventStatus.CREATED, interactor_event_content))
        elif interactor_event_content.interaction_status == "C":
            memory = await self.call("ShortTimeMemoryManager", CallMessage(CallType.Memory_GET,
                                                                           [MemoryType.Instruction, MemoryType.Plan,
                                                                            MemoryType.ActionResult, MemoryType.KeyInfo,
                                                                            MemoryType.UserInteraction,
                                                                            MemoryType.ScreenPerception]))
            await self.publish("app_channel", EventMessage(EventType.UserInteraction, EventStatus.DONE, interactor_event_content))
        logger.info("[Interact With User] TASK completed.")

    @staticmethod
    def get_user_interaction_type_desc(user_interaction_type):
        match user_interaction_type:
            case 1:
                return "1 - Confirmation of sensitive or dangerous action"
            case 2:
                return "2 - Confirmation of irreversible action"
            case 3:
                return "3 - Choice of different options"
            case 4:
                return "4 - Further clarification of instruction"

    def build_init_prompt(self,
                          instruction,
                          plan_info: PlanInfo,
                          progress_info: ProgressInfo,
                          key_infos: list,
                          user_interaction_list: List[UserInteractionInfo],
                          current_screen_perception_info: ScreenPerceptionInfo) -> str:
        prompt = f"You have just started or have completed several interactions with the user, and this is the detail of this interaction:" \
                 f"- Interaction Type: {self.get_user_interaction_type_desc(plan_info.user_interaction_type)}\n" \
                 f"- Historical User Prompt and Response:\n"
        for user_interaction in user_interaction_list[:-1]:
            prompt += f"User Prompt:{user_interaction.action_instruction} | " \
                      f"User Response:{user_interaction.user_response}\n"

        prompt += f"- Current User Prompt and Response:\n" \
                  f"User Prompt:{user_interaction_list[-1].action_instruction} | " \
                  f"User Response:{user_interaction_list[-1].user_response}\n" \
                  f"\n"

        prompt += f"This is the user instruction, plan and progress before interacting with the user:\n" \
                  f"- Instruction: {instruction}\n" \
                  f"- Overall Plan: {plan_info.overall_plan}\n" \
                  f"- Sub-goal: {plan_info.current_sub_goal}\n" \
                  f"- History Progress Status: {progress_info.progress_status if progress_info is not None else 'No progress yet.'}\n" \
                  f"\n"

        prompt += f"The following key information is currently available for interaction with users:" \
                  f"- Key Information: {key_infos}\n" \
                  f"\n"

        prompt += f"---\n"\
                  f"Please follow the steps below to perform the action:\n" \
                  f"1. Please determine the current status of the interaction with the user: \n"\
                  f"Note: For Interaction Type 3, please check if further information needs to be collected for user decision making. Please ensure that the possible options have been fully investigated (where there are more than 10 options available, only 10 options are required). \n"\
                  f"- A: Target completed; \n"\
                  f"- B: Target not completed, need to begin or continue interaction with user; \n"\
                  f"- C: Target not completed, need to gather more information to interact with the user (optional for Interaction Type 3 only); \n"\
                  f"2. If the Interaction status is A, summarize the history with the current user's response. \n"\
                  f"3. If the Interaction Status is B, construct a prompt and interact with the user, carefully explaining what is needed from the user (to continue); \n"\
                  f"4. If the Interaction Status is C, carefully specify in the instructions what information needs to be collected in order for the user to make a decision; \n"\
                  f"\n"

        prompt += f"---\n"\
                  f"Please provide a JSON with 3 keys, which are interpreted as follows:\n"\
                  f"- interaction_status: Please use A, B and C to indicate;\n" \
                  f"- interaction_thought: Explain in detail your reasons for choosing the Interaction Status;\n"\
                  f"- action_instruction: If the interaction status is A, please fill in 'None'; if the interaction status is B, please fill in the prompt words that can help the user to make an answer or a choice; if the interaction status is C, please fill in the instruction about information collection;\n"\
                  f"- user_response: If the interaction status is A, please fill in a summary of all user responses; otherwise fill in 'None'.\n"\
                  f"Make sure this JSON can be loaded correctly by json.load().\n" \
                  f"\n"
        return prompt

    def parse_response(self, response: str) -> UserInteractionInfo:
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        response_jsonobject = json.loads(response)

        user_interaction_info = UserInteractionInfo(response_jsonobject['interaction_status'], response_jsonobject['interaction_thought'], response_jsonobject['action_instruction'], response_jsonobject['user_response'])

        return user_interaction_info
