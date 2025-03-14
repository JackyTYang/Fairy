import json
from typing import List
import re
from loguru import logger


from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Citlali.utils.image import Image
from Fairy.info_entity import PlanInfo, ProgressInfo, ScreenPerceptionInfo, ActionInfo
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventStatus, EventType, CallType, MemoryType
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

        logger.debug("Execute Plan task in progress...")

        # 从ShortTimeMemoryManager获取Instruction
        memory = await self.call("ShortTimeMemoryManager", CallMessage(CallType.Memory_GET,
                                                                       [MemoryType.Instruction, MemoryType.Action,
                                                                        MemoryType.ActionResult,
                                                                        MemoryType.ScreenPerception]))
        memory = await memory

        event_content = await self.request_llm(
            self.build_prompt(
                memory[MemoryType.Instruction],  # Instruction
                message.event_content,  # PlanInfo
                memory[MemoryType.Action][-5:],  # ActionInfoList
                memory[MemoryType.ActionResult][-5:],  # ProgressInfoList
                memory[MemoryType.ScreenPerception][-1]  # CurrentScreenPerceptionInfo
            ),
            [memory[MemoryType.ScreenPerception][-1].screenshot_file_info.get_screenshot_Image_file()]
        )

        await self.publish("app_channel", EventMessage(EventType.ActionExecution, EventStatus.CREATED, event_content))

    @staticmethod
    def build_prompt(instruction,
                     plan_info: PlanInfo,
                     action_info_list: List[ActionInfo],
                     progress_info_list: List[ProgressInfo],
                     current_screen_perception_info: ScreenPerceptionInfo) -> str:
        prompt = "### User Instruction ###\n"
        prompt += f"{instruction}\n\n"

        prompt += "### Overall Plan ###\n"
        prompt += f"{plan_info.plan}\n\n"

        prompt += "### Progress Status ###\n"
        if len(progress_info_list) > 0:
            prompt += f"{progress_info_list[-1].progress_status}\n\n"
        else:
            prompt += "No progress yet.\n\n"

        prompt += "### Current Subgoal ###\n"
        prompt += f"{plan_info.current_sub_goal}\n\n"

        prompt += "### Screen Information ###\n"
        prompt += (
            f"The attached image is a screenshot showing the current state of the phone. "
            f"Its width and height are {current_screen_perception_info.perception_infos.width} and {current_screen_perception_info.perception_infos.height} pixels, respectively.\n"
        )
        prompt += (
            "To help you better understand the content in this screenshot, we have extracted positional information for the text elements and icons, including interactive elements such as search bars. "
            "The format is: (coordinates; content). The coordinates are [x, y], where x represents the horizontal pixel position (from left to right) "
            "and y represents the vertical pixel position (from top to bottom)."
        )
        prompt += "The extracted information is as follows:\n"

        for clickable_info in current_screen_perception_info.perception_infos.infos:
            if clickable_info['text'] != "" and clickable_info['text'] != "icon: None" and clickable_info[
                'coordinates'] != (0, 0):
                prompt += f"{clickable_info['coordinates']}; {clickable_info['text']}\n"
        prompt += "\n"
        prompt += (
            "Note that a search bar is often a long, rounded rectangle. If no search bar is presented and you want to perform a search, you may need to tap a search button, which is commonly represented by a magnifying glass.\n"
            "Also, the information above might not be entirely accurate. "
            "You should combine it with the screenshot to gain a better understanding."
        )
        prompt += "\n\n"

        prompt += "### Keyboard status ###\n"
        if current_screen_perception_info.perception_infos.keyboard_status:
            prompt += "The keyboard has been activated and you can type."
        else:
            prompt += "The keyboard has not been activated and you can\'t type."
        prompt += "\n\n"

        prompt += "---\n"
        prompt += "Carefully examine all the information provided above and decide on the next action to perform. If you notice an unsolved error in the previous action, think as a human user and attempt to rectify them. You must choose your action from one of the atomic actions or the shortcuts. The shortcuts are predefined sequences of actions that can be used to speed up the process. Each shortcut has a precondition specifying when it is suitable to use. If you plan to use a shortcut, ensure the current phone state satisfies its precondition first.\n\n"

        prompt += "#### Atomic Actions ####\n"
        prompt += "The atomic action functions are listed in the format of `name(arguments): description` as follows:\n"

        info = {
            "width": current_screen_perception_info.perception_infos.width,
            "height": current_screen_perception_info.perception_infos.height,
        }
        if current_screen_perception_info.perception_infos.keyboard_status:
            for action, value in ATOMIC_ACTION_SIGNITURES.items():
                prompt += f"- {action}({', '.join(value['arguments'])}): {value['description'](info)}\n"
        else:
            for action, value in ATOMIC_ACTION_SIGNITURES.items():
                if action != AtomicActionType.Type:
                    prompt += f"- {action}({', '.join(value['arguments'])}): {value['description'](info)}\n"
            prompt += "NOTE: Unable to type. The keyboard has not been activated. To type, please activate the keyboard by tapping on an input box or using a shortcut, which includes tapping on an input box first.”\n"

        prompt += "### Latest Action History ###\n"
        # if message.action_history != []:
        if len(action_info_list) > 0:
            prompt += "Recent actions you took previously and whether they were successful:\n"
            # num_actions = min(5, len(message.action_history))
            # latest_actions = message.action_history[-num_actions:]
            # latest_summary = message.summary_history[-num_actions:]
            # latest_outcomes = message.action_outcomes[-num_actions:]
            # error_descriptions = message.error_descriptions[-num_actions:]

            action_log_strs = []
            for progress_info, action_info in zip(progress_info_list, action_info_list):
                if progress_info.outcome == "A":
                    action_log_str = f"Action: {action_info.action} | Description: {action_info.expectation} | Outcome: Successful\n"
                else:
                    action_log_str = f"Action: {action_info.action} | Description: {action_info.expectation} | Outcome: Failed | Feedback: {progress_info.error_description}\n"
                prompt += action_log_str
                action_log_strs.append(action_log_str)

            if progress_info_list[-1].outcome == "C" and "Tap" in action_log_strs[-1] and "Tap" in action_log_strs[-2]:
                prompt += "\nHINT: If multiple Tap actions failed to make changes to the screen, consider using a \"Swipe\" action to view more content or use another way to achieve the current subgoal."

            # for act, summ, outcome, err_des in zip(latest_actions, latest_summary, latest_outcomes, error_descriptions):
            #     if outcome == "A":
            #         action_log_str = f"Action: {act} | Description: {summ} | Outcome: Successful\n"
            #     else:
            #         action_log_str = f"Action: {act} | Description: {summ} | Outcome: Failed | Feedback: {err_des}\n"
            #     prompt += action_log_str
            #     action_log_strs.append(action_log_str)
            # if latest_outcomes[-1] == "C" and "Tap" in action_log_strs[-1] and "Tap" in action_log_strs[-2]:
            #     prompt += "\nHINT: If multiple Tap actions failed to make changes to the screen, consider using a \"Swipe\" action to view more content or use another way to achieve the current subgoal."

            prompt += "\n"
        else:
            prompt += "No actions have been taken yet.\n\n"

        prompt += "---\n"
        prompt += "Provide your output in the following format, which contains three parts:\n"
        prompt += "### Thought ###\n"
        prompt += "Provide a detailed explanation of your rationale for the chosen action. IMPORTANT: If you decide to use a shortcut, first verify that its precondition is met in the current phone state. For example, if the shortcut requires the phone to be at the Home screen, check whether the current screenshot shows the Home screen. If not, perform the appropriate atomic actions instead.\n\n"

        prompt += "### Action ###\n"
        prompt += "Choose only one action or shortcut from the options provided. IMPORTANT: Do NOT return invalid actions like null or stop. Do NOT repeat previously failed actions.\n"
        prompt += "Use shortcuts whenever possible to expedite the process, but make sure that the precondition is met.\n"
        prompt += "You must provide your decision using a valid JSON format specifying the name and arguments of the action. For example, if you choose to tap at position (100, 200), you should write {\"name\":\"Tap\", \"arguments\":{\"x\":100, \"y\":100}}. If an action does not require arguments, such as Home, fill in null to the \"arguments\" field. Ensure that the argument keys match the action function's signature exactly. Please ensure that the output can be directly loaded by the Python json.load() function\n\n"

        prompt += "### Description ###\n"
        prompt += "A brief description of the chosen action and the expected outcome."
        return prompt

    def parse_response(self, response: str) -> ActionInfo | None:
        thought = (response.split("### Thought ###")[-1].split("### Action ###")[0]
                   .replace("\n", " ").replace("  ", " ").strip())
        action = (response.split("### Action ###")[-1].split("### Description ###")[0]
                  .replace("\n", " ").replace("  ", " ").strip())
        expectation = (response.split("### Description ###")[-1]
                       .replace("\n", " ").replace("  ", " ").strip())

        print(action)
        if "json" in action:
            action = re.search(r"```json\s*(.*?)\s*```", action, re.DOTALL).group(1)
        print(action)

        action_object = json.loads(action)
        action, arguments = action_object["name"], action_object["arguments"]

        # execute atomic action
        try:
            action = AtomicActionType(action)
            return ActionInfo(thought, action, expectation, arguments)
        except ValueError:
            if action.lower() in ["null", "none", "finish", "exit", "stop"]:
                print("Agent choose to finish the task. Action: ", action)
                return ActionInfo(thought, AtomicActionType.Stop, expectation, {})
            else:
                print("Error! Invalid action name: ", action)
                return None
