import json
from typing import List
import re
from loguru import logger


from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.fairy_config import FairyConfig
from Fairy.info_entity import PlanInfo, ProgressInfo, ScreenInfo, ActionInfo
from Fairy.memory.long_time_memory_manager import LongMemoryCallType
from Fairy.memory.short_time_memory_manager import ActionMemoryType, ShortMemoryCallType
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventStatus, EventType, CallType
from Fairy.tools.mobile_controller.action_type import ATOMIC_ACTION_SIGNITURES, AtomicActionType


class AppExecutorAgent(Agent):
    def __init__(self, runtime, config: FairyConfig) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to choose the correct actions to complete the user's instruction. Think as if you are a human user operating the phone.",
            type="SystemMessage")]
        super().__init__(runtime, "AppExecutorAgent", config.model_client, system_messages)
        self.non_visual_mode = config.non_visual_mode

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.Plan and msg.status == EventStatus.DONE)
    async def on_execute_plan(self, message: EventMessage, message_context):

        logger.bind(log_tag="fairy_sys").info("[Execute Plan] TASK in progress...")

        # 如果当前Plan需要用户交互，则跳过
        print(message.event_content.user_interaction_type)
        if message.event_content.user_interaction_type != 0:
            logger.bind(log_tag="fairy_sys").info("[Execute Plan] User interaction required, skipped")
            return

        # 从ShortTimeMemoryManager获取Instruction\Current Action Memory (Plan, StartScreenPerception)\Historical Action Memory (Action, ActionResult)\KeyInfo
        short_memory = await (await self.call(
            "ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET,{
                ShortMemoryCallType.GET_Instruction:None,
                ShortMemoryCallType.GET_Current_Action_Memory:[ActionMemoryType.Plan, ActionMemoryType.StartScreenPerception],
                ShortMemoryCallType.GET_Historical_Action_Memory:{ActionMemoryType.Action:5, ActionMemoryType.ActionResult:5},
                ShortMemoryCallType.GET_Key_Info:None
            })
        ))
        instruction_memory = short_memory[ShortMemoryCallType.GET_Instruction]
        current_action_memory = short_memory[ShortMemoryCallType.GET_Current_Action_Memory]
        historical_action_memory = short_memory[ShortMemoryCallType.GET_Historical_Action_Memory]
        key_info_memory = short_memory[ShortMemoryCallType.GET_Key_Info]

        # 获取上次任务的完成状态
        last_action_result = historical_action_memory[ActionMemoryType.ActionResult][-1].action_result if len(historical_action_memory[ActionMemoryType.ActionResult])>0 else None
        if last_action_result is not None and (last_action_result == "C" or last_action_result == "D"):
            # 如果上次任务失败，则需要提取纠错Tips
            long_memory = await (await self.call(
                "LongTimeMemoryManager",
                CallMessage(CallType.Memory_GET, {
                    LongMemoryCallType.GET_Execution_ERROR_Tips: historical_action_memory[ActionMemoryType.ActionResult][-1].error_potential_causes,
                })
            ))
            execution_tips = long_memory[LongMemoryCallType.GET_Execution_ERROR_Tips]
        else:
            # 如果上次任务成功，则需要提取执行Tips
            # 提取当前的Sub-goal
            sub_goal = current_action_memory[ActionMemoryType.Plan].current_sub_goal
            # 从LongTimeMemoryManager获取Tips
            long_memory = await (await self.call(
                "LongTimeMemoryManager",
                CallMessage(CallType.Memory_GET,{
                    LongMemoryCallType.GET_Execution_Tips: sub_goal,
                })
            ))
            execution_tips = long_memory[LongMemoryCallType.GET_Execution_Tips]

        images = []
        if not self.non_visual_mode:
            images.append(current_action_memory[ActionMemoryType.StartScreenPerception].screenshot_file_info.get_screenshot_Image_file())

        event_content = await self.request_llm(
            self.build_prompt(
                instruction_memory,
                current_action_memory[ActionMemoryType.Plan],
                current_action_memory[ActionMemoryType.StartScreenPerception],
                historical_action_memory[ActionMemoryType.Action],
                historical_action_memory[ActionMemoryType.ActionResult],
                execution_tips,
                key_info_memory,
            ),
            images=images
        )

        await self.publish("app_channel", EventMessage(EventType.ActionExecution, EventStatus.CREATED, event_content))
        logger.bind(log_tag="fairy_sys").info("[Execute Plan] TASK completed.")

    @staticmethod
    def build_prompt(instruction,
                     plan_info: PlanInfo,
                     current_screen_perception_info: ScreenInfo,
                     action_info_list: List[ActionInfo],
                     progress_info_list: List[ProgressInfo],
                     execution_tips: str,
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
            prompt += f"IMPORTANT: You should NOT REPEAT Action where the Action Result is Failure. Please be especially CAREFUL to check that the operation you are going to do this time does NOT lead to a REPEAT of the error.\n"
            prompt += "\n\n"
        else:
            prompt += "No actions have been taken yet.\n\n"

        prompt += f"---\n" \
                  f"Here's some TIPS for execution the action. These TIPS are VERY IMPORTANT, so MAKE SURE you follow them to the letter!\n" \
                  f"{execution_tips}\n" \
                  f"\n"

        prompt += "---\n"
        prompt += "Please provide a JSON with 3 keys, which are interpreted as follows:\n"\
                  "- action_thought: A detailed explanation of your rationale for the chosen action.\n"\
                  "- actions: ONE or MORE action from the 'Atomic Actions' provided. IMPORTANT: DO NOT return invalid actions like null or stop. DO NOT repeat previously failed actions. The decided action must be provided in a valid JSON format and should be an array containing a sequence of actions, specifying the name and parameters of the action. For example, if you decide to tap on position (100, 200) first, you should first put in the array \{\"name\":\"Tap\", \"arguments\":{\"x\":100, \"y\":100}}. If an action does not require parameters, such as 'Wait', fill in the 'Parameters' field with null. IMPORTANT: MAKE SURE the parameter key matches the signature of the action function exactly. MAKE SURE that the order of the actions in the array is the same as the order in which you want them to be executed. MAKE SURE this JSON can be loaded correctly by json.load().\n"\
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
