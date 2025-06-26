import json
from typing import List
import re
from loguru import logger


from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.config.fairy_config import FairyConfig
from Fairy.entity.info_entity import PlanInfo, ProgressInfo, ScreenInfo, ActionInfo
from Fairy.entity.log_template import LogTemplate, LogEventType
from Fairy.memory.long_time_memory_manager import LongMemoryCallType, LongMemoryType
from Fairy.memory.short_time_memory_manager import ActionMemoryType, ShortMemoryCallType
from Fairy.entity.message_entity import EventMessage, CallMessage
from Fairy.entity.type import EventType, CallType, EventChannel, EventStatus
from Fairy.tools.mobile_controller.action_type import ATOMIC_ACTION_SIGNITURES, AtomicActionType


class AppActionDeciderAgent(Agent):
    def __init__(self, runtime, config: FairyConfig) -> None:
        system_messages = [ChatMessage(
            content="You are part of a helpful AI assistant for operating mobile phones and your identity is an action decider. Your goal is to choose the correct atomic actions to complete the user's instruction. Think as if you are a human user operating the phone.",
            type="SystemMessage")]
        super().__init__(runtime, " AppActionDeciderAgent", config.model_client, system_messages)
        self.log_t = LogTemplate(self)  # 日志模板

        self.non_visual_mode = config.non_visual_mode
        self.convert_marks_to_coordinates = None

    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.APP_CHANNEL,
              listen_filter=lambda msg: msg.match(EventType.Plan, EventStatus.DONE))
    async def on_execute_plan(self, message: EventMessage, message_context):
        # 发布ActionDecision CREATED事件 & 记录日志
        await self.publish(EventChannel.APP_CHANNEL, EventMessage(EventType.ActionDecision, EventStatus.CREATED))
        logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerStart)("Action Decision"))

        # 如果当前Plan需要用户交互，则跳过
        if str(message.event_content.user_interaction_type) != "0":
            logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerSkip)("Action Decision", "User interaction required."))
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
                    LongMemoryCallType.GET_Tips: {
                        LongMemoryType.Execution_ERROR_Tips: {
                            "query": historical_action_memory[ActionMemoryType.ActionResult][-1].error_potential_causes,
                            "app_package_name": instruction_memory.app_package_name
                        }
                    }
                })
            ))
            execution_tips = long_memory[LongMemoryCallType.GET_Tips][LongMemoryType.Execution_ERROR_Tips]
        else:
            # 如果上次任务成功，则需要提取执行Tips
            # 提取当前的Sub-goal
            sub_goal = current_action_memory[ActionMemoryType.Plan].current_sub_goal
            # 从LongTimeMemoryManager获取Tips
            long_memory = await (await self.call(
                "LongTimeMemoryManager",
                CallMessage(CallType.Memory_GET, {
                    LongMemoryCallType.GET_Tips: {
                        LongMemoryType.Execution_Tips: {
                            "query": sub_goal,
                            "app_package_name": instruction_memory.app_package_name
                        }
                    }
                })
            ))
            execution_tips = long_memory[LongMemoryCallType.GET_Tips][LongMemoryType.Execution_Tips]

        images = []
        start_screen_perception = current_action_memory[ActionMemoryType.StartScreenPerception]
        if not self.non_visual_mode:
            images.append(start_screen_perception.screenshot_file_info.get_screenshot_Image_file())
            screenshot_prompt = "The attached image is a screenshots of your phone to show the current state"
        else:
            screenshot_prompt = "The following text description (e.g. JSON or XML) is converted from a screenshots of your phone to show the current state"

        if start_screen_perception.perception_infos.use_set_of_marks_mapping:
            self.convert_marks_to_coordinates = start_screen_perception.perception_infos.convert_marks_to_coordinates

        action_info = await self.request_llm(
            self.build_prompt(
                instruction_memory.get_instruction(),
                instruction_memory.language,
                current_action_memory[ActionMemoryType.Plan],
                start_screen_perception,
                historical_action_memory[ActionMemoryType.Action],
                historical_action_memory[ActionMemoryType.ActionResult],
                execution_tips,
                key_info_memory,
                screenshot_prompt
            ),
            images=images
        )

        logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.IntermediateResult)("Action decision result", action_info))

        # 发布ActionDecision Done事件 & 记录日志
        await self.publish(EventChannel.APP_CHANNEL, EventMessage(EventType.ActionDecision, EventStatus.DONE, action_info))
        logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerCompleted)("Action Decision"))

    def build_prompt(self,
                     instruction,
                     ins_language,
                     plan_info: PlanInfo,
                     current_screen_perception_info: ScreenInfo,
                     action_info_list: List[ActionInfo],
                     progress_info_list: List[ProgressInfo],
                     execution_tips: str,
                     key_infos: list,
                     screenshot_prompt: str) -> str:
        prompt = f"---\n" \
                 f"- Instruction: {instruction}\n" \
                 f"- Overall Plan: {plan_info.overall_plan}\n" \
                 f"- Current Sub-goal: {plan_info.current_sub_goal}\n" \
                 f"- Key Information Record (Excluding Current Screen): {key_infos}\n" \
                 f"\n"

        prompt += f"---\n"
        prompt += current_screen_perception_info.perception_infos.get_screen_info_note_prompt(screenshot_prompt) # Call this function to supplement the prompt "Size of the Image and Additional Information".
        prompt += f"\n"

        prompt += current_screen_perception_info.perception_infos.get_screen_info_prompt() # Call this function to get the content of the prompt "Screen Perception Information and Keyboard Status".

        prompt += f"Please scrutinize the above screen information to infer the type of the current page (e.g., home page, search page, results page, details page, etc.) and thus the main function of the page. This helps you to avoid wrong actions."\
                  f"\n"

        prompt += "---\n"
        prompt += "Carefully examine all the information provided above and decide on the next action to perform. If you notice an unsolved error in the previous action, think as a human user and attempt to rectify them. You must choose your action from ONE or MORE of the atomic actions.\n"\
                  "If there are multiple options and the user does not specify which one to choose in the Instruction, interaction with the user is necessary. You cannot make any choices on behalf of the user.\n"\
                  "\n"

        prompt += "- Atomic Actions: \n"
        prompt += "The atomic action functions are listed in the format of `name(arguments): description` as follows:\n"
        if self.convert_marks_to_coordinates is not None:
            for action, value in ATOMIC_ACTION_SIGNITURES.items():
                prompt += f"- {action}({', '.join(value['SoM_arguments'])}): {value['description'](True)}\n"
        else:
            for action, value in ATOMIC_ACTION_SIGNITURES.items():
                prompt += f"- {action}({', '.join(value['arguments'])}): {value['description'](False)}\n"

        prompt += f"IMPORTANT: When you input something (especially a search), please be careful to use the language {ins_language}.\n" \
                  "\n"
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
        prompt += "Please provide a JSON with 4 keys, which are interpreted as follows:\n"\
                  "- action_thought: A detailed explanation of your rationale for the chosen action.\n"\
                  "- actions: ONE or MORE action from the 'Atomic Actions' provided. IMPORTANT: DO NOT return invalid actions like null or stop. DO NOT repeat previously failed actions. The decided action must be provided in a valid JSON format and should be an array containing a sequence of actions, specifying the name and parameters of the action. For example, if you decide to tap on position (100, 200) first, you should first put in the array \{\"name\":\"Tap\", \"arguments\":{\"x\":100, \"y\":100}}. If an action does not require parameters, such as 'Wait', fill in the 'Parameters' field with null. IMPORTANT: MAKE SURE the parameter key matches the signature of the action function exactly. MAKE SURE that the order of the actions in the array is the same as the order in which you want them to be executed. MAKE SURE this JSON can be loaded correctly by json.load().\n"\
                  f"- action_expectation: A brief description of the expected results of the selected action(s).\n" \
                  f"- user_interaction_thought: A judgment on whether or not need to interact with the user and explain the reasons. \n" \
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

        if self.convert_marks_to_coordinates is not None:
            logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.IntermediateResult)("Original action decision (before converting markers to coordinates) result", response_jsonobject['actions']))
            response_jsonobject['actions'] = self.SoM_args_conversion(response_jsonobject['actions'], self.convert_marks_to_coordinates)

        action_info = ActionInfo(response_jsonobject['action_thought'], response_jsonobject['actions'], response_jsonobject['action_expectation'], response_jsonobject['user_interaction_thought'])
        return action_info

    def SoM_args_conversion(self, actions, convert_marks_to_coordinates):
        args = []
        for action in actions:
            match AtomicActionType(action['name']):
                case AtomicActionType.Tap:
                    coordinate = convert_marks_to_coordinates(action['arguments']['mark_number'])
                    args.append({'name': action['name'], 'arguments': {'x': coordinate[0], 'y': coordinate[1]}})
                case AtomicActionType.LongPress:
                    coordinate = convert_marks_to_coordinates(action['arguments']['mark_number'])
                    args.append({'name': action['name'], 'arguments': {'x': coordinate[0], 'y': coordinate[1]}, 'duration': action['arguments']['duration']})
                case AtomicActionType.Swipe:
                    (x1, y1), (x2, y2) = convert_marks_to_coordinates(action['arguments']['mark_number'])
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    width = x2 - x1
                    height = y2 - y1
                    distance = action['arguments']['distance']
                    match action['arguments']['direction']:
                        case 'H':
                            dy = height * abs(distance) / 2
                            start_y = center_y + dy if distance > 0 else center_y - dy
                            end_y = center_y - dy if distance > 0 else center_y + dy
                            args.append({'name': action['name'], 'arguments': {'x1': center_x, 'y1': start_y, 'x2': center_x, 'y2': end_y}})
                        case 'W':
                            dx = width * abs(distance) / 2
                            start_x = center_x + dx if distance > 0 else center_x - dx
                            end_x = center_x - dx if distance > 0 else center_x + dx
                            args.append({'name': action['name'], 'arguments': {'x1': start_x, 'y1': center_y, 'x2': end_x, 'y2': center_y}})
                        case _:
                            raise RuntimeError(f"Invalid direction: {action['arguments']['direction']}. Must be 'H' or 'W'.")
                case _:
                    args.append(action)
        return args
