import json
import re
from typing import List

from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.fairy_config import FairyConfig
from Fairy.info_entity import PlanInfo, ScreenInfo, UserInteractionInfo
from Fairy.memory.short_time_memory_manager import ShortMemoryCallType, ActionMemoryType
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventType, EventStatus, CallType


class UserInteractorAgent(Agent):
    def __init__(self, runtime, config: FairyConfig) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to interact with the user. Think as if you are a human user operating the phone.",
            type="SystemMessage")]
        super().__init__(runtime, "UserInteractorAgent", config.model_client, system_messages)
        self.non_visual_mode = config.non_visual_mode

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.Plan and msg.status == EventStatus.DONE)
    async def on_user_interact(self, message: EventMessage, message_context):
        if str(message.event_content.user_interaction_type) != "0":
            await self._on_user_interact(message, message_context)
        else:
            logger.bind(log_tag="fairy_sys").info("[Interact With User] No user interaction required, skipped")

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: (msg.event == EventType.UserChat or msg.event == EventType.TaskFinish) and msg.status == EventStatus.DONE and type(msg.event_content) == UserInteractionInfo)
    async def on_user_interact_reflect(self, message: EventMessage, message_context):
        await self._on_user_interact(message, message_context)

    async def _on_user_interact(self, message: EventMessage, message_context):
        logger.bind(log_tag="fairy_sys").info("[Interact With User] TASK in progress...")

        # 从ShortTimeMemoryManager获取Instruction\Current Action Memory (Plan, StartScreenPerception)\Historical Action Memory (Action, ActionResult)\KeyInfo
        memory = await (await self.call(
            "ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET,{
                ShortMemoryCallType.GET_Instruction:None,
                ShortMemoryCallType.GET_Current_Action_Memory:[ActionMemoryType.Plan, ActionMemoryType.StartScreenPerception],
                ShortMemoryCallType.GET_Key_Info:None,
                ShortMemoryCallType.GET_Current_User_Interaction: None
            })
        ))
        instruction_memory = memory[ShortMemoryCallType.GET_Instruction]
        current_action_memory = memory[ShortMemoryCallType.GET_Current_Action_Memory]
        key_info_memory = memory[ShortMemoryCallType.GET_Key_Info]
        current_user_interaction = memory[ShortMemoryCallType.GET_Current_User_Interaction]
        # 构建Prompt
        images = []
        if not self.non_visual_mode:
            images.append(current_action_memory[ActionMemoryType.StartScreenPerception].screenshot_file_info.get_screenshot_Image_file())
            screenshot_prompt = "The attached image is a screenshots of your phone to show the current state"
        else:
            screenshot_prompt = "The following text description (e.g. JSON or XML) is converted from a screenshots of your phone to show the current state"

        interactor_event_content = await self.request_llm(
            self.build_init_prompt(instruction_memory,
                                   current_action_memory[ActionMemoryType.Plan],
                                   current_action_memory[ActionMemoryType.StartScreenPerception],
                                   key_info_memory,
                                   current_user_interaction,
                                   screenshot_prompt),
            images=images,
        )

        if interactor_event_content.interaction_status == "A":
            await self.publish("app_channel", EventMessage(EventType.UserInteraction, EventStatus.DONE, interactor_event_content))
        elif interactor_event_content.interaction_status == "B":
            await self.publish("app_channel", EventMessage(EventType.UserChat, EventStatus.CREATED, interactor_event_content))
        elif interactor_event_content.interaction_status == "C":
            await self.publish("app_channel", EventMessage(EventType.Task, EventStatus.CREATED, {
                "instruction": interactor_event_content.action_instruction,
                "thought": interactor_event_content.interaction_thought,
                "task_name": "More Info Explore",
                "source": "UserInteractorAgent"
            }))
        logger.bind(log_tag="fairy_sys").info("[Interact With User] TASK completed.")

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
                          current_screen_perception_info: ScreenInfo,
                          key_infos: list,
                          user_interaction_list: List[UserInteractionInfo],
                          screenshot_prompt: str) -> str:
        prompt = f"You have just started or have completed several interactions with the user, and this is the detail of this interaction:\n" \
                 f"- Interaction Type: {self.get_user_interaction_type_desc(plan_info.user_interaction_type)}\n" \
                 f"- Interaction Thought: {plan_info.user_interaction_thought}\n"

        prompt += f"- Historical User Prompt and Response:\n"
        if len(user_interaction_list[:-2])>0:
            for user_interaction in user_interaction_list[:-2]:
                prompt += f"User Prompt:{user_interaction.action_instruction} | " \
                          f"User Response:{user_interaction.response}\n"
        else:
            prompt += f"No history of interactions.\n"

        prompt += f"- Current User Prompt and Response:\n"
        if len(user_interaction_list) > 0:
            prompt += f"User Prompt:{user_interaction_list[-1].action_instruction} | " \
                      f"User Response:{user_interaction_list[-1].response}\n"
        else:
            prompt += f"This is the first interaction.\n"

        prompt += f"\n"

        prompt += f"This is the user instruction, plan before interacting with the user:\n" \
                  f"- Instruction: {instruction}\n" \
                  f"- Overall Plan: {plan_info.overall_plan}\n" \
                  f"- Sub-goal: {plan_info.current_sub_goal}\n" \
                  f"\n"

        prompt += f"---\n"
        prompt += current_screen_perception_info.perception_infos.get_screen_info_note_prompt(screenshot_prompt) # Call this function to supplement the prompt "Size of the Image and Additional Information".
        prompt += f"\n"

        prompt += current_screen_perception_info.perception_infos.get_screen_info_prompt() # Call this function to get the content of the prompt "Screen Perception Information and Keyboard Status".

        prompt += f"---\n"\
                  f"The following key information is currently available for interaction with users:\n" \
                  f"- Key Information: {key_infos}\n" \
                  f"\n"

        prompt += f"---\n"\
                  f"Please follow the steps below to perform the action:\n" \
                  f"1. Please check the 'Current User Prompt and Response' (if any) to determine the current status of the interaction with the user: \n"\
                  f"Note: For Interaction Type 3, please check if further information needs to be collected for user decision making. Please ensure that the possible options have been fully investigated (where there are more than 10 options available, only 10 options are required). \n"\
                  f"- A: Interaction Target completed, the user has made a clear choice or has clarified the instruction and can end the user interaction; \n"\
                  f"- B: Interaction Target not completed, need to begin or continue interaction with user; \n"\
                  f"- C: Interaction Target not completed, 'user requests for more options' OR 'user selects option not offered' OR 'need to gather more information to interact with the user' (optional for Interaction Type 3 only); \n"\
                  f"2. If the Interaction Status is A, summarize the history with the current user's response. \n"\
                  f"3. If the Interaction Status is B, construct a prompt and interact with the user, carefully explaining what is needed from the user (to continue), ask the user to answer yes or no if confirmation is required, please use the language of the user instructions; \n"\
                  f"4. If the Interaction Status is C, carefully specify in the instructions what information needs to be collected in order for the user to make a decision; \n"\
                  f"\n"

        prompt += f"---\n"\
                  f"Please provide a JSON with 3 keys, which are interpreted as follows:\n"\
                  f"- interaction_status: Please use A, B and C to indicate;\n" \
                  f"- interaction_thought: Explain in detail your reasons for choosing the Interaction Status;\n" \
                  f"- response: If the Interaction Status is A, please fill in a summary of all responses; otherwise fill in 'None'.\n" \
                  f"- user_prompt: If the Interaction Status is B, please fill in the prompt words that can help the user to make an answer or a choice (Includes available options), you shouldn't let the user perform any actions on their own, simply ask Yes or No when the user interaction type is 1 or 2; Otherwise, please fill in 'None'. \n" \
                  f"- action_instruction: If the Interaction Status is C, please fill in the instruction for a new Agent to collect information gathering, need to include information specifically to be collected and quantities; Otherwise, please fill in 'None'.\n" \
                  f"Make sure this JSON can be loaded correctly by json.load().\n" \
                  f"\n"
        return prompt

    def parse_response(self, response: str) -> UserInteractionInfo:
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        response_jsonobject = json.loads(response)

        if response_jsonobject['interaction_status'] == "C":
            action_instruction = response_jsonobject['action_instruction']
        elif response_jsonobject['interaction_status'] == "B":
            action_instruction = response_jsonobject['user_prompt']
        else:
            action_instruction = None

        user_interaction_info = UserInteractionInfo(response_jsonobject['interaction_status'],
                                                    response_jsonobject['interaction_thought'],
                                                    action_instruction,
                                                    response_jsonobject['response'])
        return user_interaction_info
