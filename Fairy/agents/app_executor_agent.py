import json
from typing import List
import re
from loguru import logger


from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.info_entity import PlanInfo, ProgressInfo, ScreenPerceptionInfo, ActionInfo
from Fairy.memory.short_time_memory_manager import ActionMemoryType, MemoryCallType
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventStatus, EventType, CallType
from Fairy.tools.action_type import ATOMIC_ACTION_SIGNITURES, AtomicActionType


class AppExecutorAgent(Agent):
    def __init__(self, runtime, model_client) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to choose the correct actions to complete the user's instruction. Think as if you are a human user operating the phone.",
            type="SystemMessage")]
        super().__init__(runtime, "AppExecutorAgent", model_client, system_messages)

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.Plan and msg.status == EventStatus.DONE)
    async def on_execute_plan(self, message: EventMessage, message_context):

        logger.info("[Execute Plan] TASK in progress...")

        # 如果当前Plan需要用户交互，则跳过
        print(message.event_content.user_interaction_type)
        if message.event_content.user_interaction_type != 0:
            logger.info("[Execute Plan] User interaction required, skipped")
            return

        # 从ShortTimeMemoryManager获取Instruction\Current Action Memory (Plan, StartScreenPerception)\Historical Action Memory (Action, ActionResult)\KeyInfo
        memory = await (await self.call(
            "ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET,{
                MemoryCallType.GET_Instruction:None,
                MemoryCallType.GET_Current_Action_Memory:[ActionMemoryType.Plan, ActionMemoryType.StartScreenPerception],
                MemoryCallType.GET_Historical_Action_Memory:{ActionMemoryType.Action:5, ActionMemoryType.ActionResult:5},
                MemoryCallType.GET_Key_Info:None
            })
        ))
        instruction_memory = memory[MemoryCallType.GET_Instruction]
        current_action_memory = memory[MemoryCallType.GET_Current_Action_Memory]
        historical_action_memory = memory[MemoryCallType.GET_Historical_Action_Memory]
        key_info_memory = memory[MemoryCallType.GET_Key_Info]

        event_content = await self.request_llm(
            self.build_prompt(
                instruction_memory,
                current_action_memory[ActionMemoryType.Plan],
                current_action_memory[ActionMemoryType.StartScreenPerception],
                historical_action_memory[ActionMemoryType.Action],
                historical_action_memory[ActionMemoryType.ActionResult],
                key_info_memory,
            ),
            [current_action_memory[ActionMemoryType.StartScreenPerception].screenshot_file_info.get_screenshot_Image_file()]
        )

        await self.publish("app_channel", EventMessage(EventType.ActionExecution, EventStatus.CREATED, event_content))
        logger.info("[Execute Plan] TASK completed.")

    @staticmethod
    def build_prompt(instruction,
                     plan_info: PlanInfo,
                     current_screen_perception_info: ScreenPerceptionInfo,
                     action_info_list: List[ActionInfo],
                     progress_info_list: List[ProgressInfo],
                     key_infos: list) -> str:
        prompt = f"---\n" \
                 f"- Instruction: {instruction}\n" \
                 f"- Overall Plan: {plan_info.overall_plan}\n" \
                 f"- Current Sub-goal: {plan_info.current_sub_goal}\n" \
                 f" - Key Information Record (Excluding Current Screen): {key_infos}\n" \
                 f"\n"

        prompt += f"---\n"
        prompt += current_screen_perception_info.perception_infos.get_screen_info_note_prompt("The attached image is a screenshots of your phone to show the current state") # Call this function to supplement the prompt "Size of the Image and Additional Information".
        prompt += f"\n"

        prompt += current_screen_perception_info.perception_infos.get_screen_info_prompt() # Call this function to get the content of the prompt "Screen Perception Information and Keyboard Status".

        prompt += "---\n"
        prompt += "Carefully examine all the information provided above and decide on the next action to perform. If you notice an unsolved error in the previous action, think as a human user and attempt to rectify them. You must choose your action from ONE or MORE of the atomic actions.\n\n"
        prompt += "- Atomic Actions: \n"
        prompt += "The atomic action functions are listed in the format of `name(arguments): description` as follows:\n"

        for action, value in ATOMIC_ACTION_SIGNITURES.items():
            # if current_screen_perception_info.perception_infos.keyboard_status and action == AtomicActionType.Type:
            #     continue # Skip the Type action if the keyboard is not activated
            prompt += f"- {action}({', '.join(value['arguments'])}): {value['description']}\n"
        if not current_screen_perception_info.perception_infos.keyboard_status:
            prompt += "NOTE: Unable to input. The keyboard has not been activated. To input, please activate the keyboard by tapping on an input box, which includes tapping on an input box first.\n"\
                      "\n"

        prompt += f"---\n" \
                  f"- Latest Action History: \n"
        if len(action_info_list) > 0:
            prompt += "(Recent 5 actions you took previously and whether they were successful)\n"
            for progress_info, action_info in zip(progress_info_list, action_info_list):
                action_log_str = f"Action(s): {action_info.actions} | " \
                                 f"Action Description: {action_info.action_expectation} | " \
                                 f"Action Result: { 'Successful' if progress_info.action_result == 'A' else 'Partial Successful'  if progress_info.action_result == 'B' else 'Failure'} | "
                if progress_info.action_result == "C" or progress_info.action_result == "D":
                    action_log_str += f"Error Potential Causes: {progress_info.error_potential_causes} | "
                action_log_str += "\n"
                prompt += action_log_str
            prompt += "TIPS: If multiple Tap actions failed to make changes to the screen, consider using a \"Swipe\" action to view more content or use another way to achieve the current subgoal."
            prompt += "\n"
        else:
            prompt += "No actions have been taken yet.\n\n"

        prompt += "Here's some basic common sense for using the app, please NOTE:\n" \
                  "1. As a promotional tool, the search bar may have been pre-filled with promotional content, and clicking the search button directly may result in searching for advertisements. In this case, you can tap the body of the search bar, delete all the contents, and then input in the content you want to search.\n" \
                  "2. If the search bar is pre-filled please DO NOT tap on the SEARCH BUTTON but tap on the search bar instead.\n" \
                  "3. Search bar is often a long, rounded rectangle. If no search bar is presented and you want to perform a search, you may need to tap a search button, which is commonly represented by a magnifying glass. \n" \
                  "4. If a search bar exists, DO NOT click the search button until you have entered what you want to search for!\n"\
                  "\n"

        prompt += "---\n"
        prompt += "Please provide a JSON with 3 keys, which are interpreted as follows:\n"\
                  "- action_thought: A detailed explanation of your rationale for the chosen action.\n"\
                  "- actions: Choose ONE or MORE action from the options provided. IMPORTANT: Do NOT return invalid actions like null or stop. Do NOT repeat previously failed actions.The decided action must be provided in a valid JSON format and should be an array containing a sequence of actions, specifying the name and parameters of the action. For example, if you decide to tap on position (100, 200) first, you should first put in the array \{\"name\":\"Tap\", \"arguments\":{\"x\":100, \"y\":100}}. If an action does not require parameters, such as 'Wait', fill in the 'Parameters' field with null. IMPORTANT: MAKE SURE the parameter key matches the signature of the action function exactly. MAKE SURE that the order of the actions in the array is the same as the order in which you want them to be executed. MAKE SURE this JSON can be loaded correctly by json.load().\n"\
                  f"- action_expectation: A brief description of the expected results of the selected action(s).\n"\
                  f"Make sure this JSON can be loaded correctly by json.load().\n" \
                  f"\n"
        return prompt

    def parse_response(self, response: str) -> ActionInfo | None:

        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        response_jsonobject = json.loads(response)
        # check if the actions are valid
        for action in response_jsonobject['actions']:
            if action['name'] not in [action_type.value for action_type in AtomicActionType]:
                print(f"Error! Invalid action name: {action['name']}")
                return None

        action_info = ActionInfo(response_jsonobject['action_thought'], response_jsonobject['actions'], response_jsonobject['action_expectation'])
        return action_info
