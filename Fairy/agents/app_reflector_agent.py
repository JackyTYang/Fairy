from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.info_entity import PlanInfo, ProgressInfo, ScreenPerceptionInfo, ActionInfo
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventType, EventStatus, CallType, MemoryType


class AppReflectorAgent(Agent):
    def __init__(self, runtime, model_client) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to verify whether the last action produced the expected behavior and to keep track of the overall progress.",
            type="SystemMessage")]
        super().__init__(runtime, "AppReflectorAgent", model_client, system_messages)

        self.init_skip = False

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.Plan and message.status == EventStatus.CREATED)
    async def set_instruction(self, message: EventMessage, message_context):
        self.init_skip = True

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.ScreenPerception and msg.status == EventStatus.DONE)
    async def on_reflect(self, message:EventMessage , message_context):
        if self.init_skip:
            logger.debug("Skip reflect task.")
            self.init_skip = False
            return
        logger.debug("Reflect task in progress...")

        # 从ShortTimeMemoryManager获取Instruction
        memory = await self.call("ShortTimeMemoryManager", CallMessage(CallType.Memory_GET, [MemoryType.Instruction, MemoryType.Plan, MemoryType.Action, MemoryType.ActionResult, MemoryType.ScreenPerception]))
        memory = await memory

        event_content = await self.request_llm(
            self.build_prompt(
                memory[MemoryType.Instruction], # Instruction
                memory[MemoryType.Plan][-1], # PlanInfo
                memory[MemoryType.Action][-1],  # ActionInfo
                # ProgressInfoList can be empty if this is the first reflection
                memory[MemoryType.ActionResult][-1] if len(memory[MemoryType.ActionResult]) > 0 else None, # ProgressInfoList
                memory[MemoryType.ScreenPerception][-2], # PreviousScreenPerceptionInfo
                message.event_content # CurrentScreenPerceptionInfo
            ),
            [
                memory[MemoryType.ScreenPerception][-2].screenshot_file_info.get_screenshot_Image_file(), # PreviousScreenImageFile
                message.event_content.screenshot_file_info.get_screenshot_Image_file() # CurrentScreenImageFile
            ]
        )
        await self.publish("app_channel", EventMessage(EventType.Reflection, EventStatus.DONE, event_content))

    def build_prompt(self,
                     instruction,
                     plan_info:PlanInfo,
                     action_info: ActionInfo,
                     progress_info: ProgressInfo,
                     previous_screen_perception_info:ScreenPerceptionInfo,
                     current_screen_perception_info:ScreenPerceptionInfo) -> str:
        prompt = "### User Instruction ###\n"
        prompt += f"{instruction}\n\n"

        prompt += "### Progress Status ###\n"
        if progress_info is not None:
            prompt += f"{progress_info.progress_status}\n\n"
        else:
            prompt += "No progress yet.\n\n"

        prompt += "### Current Subgoal ###\n"
        prompt += f"{plan_info.current_sub_goal}\n\n"

        prompt += "---\n"
        prompt += f"The attached two images are two phone screenshots before and after your last action. "
        prompt += f"The width and height are {current_screen_perception_info.perception_infos.width} and {current_screen_perception_info.perception_infos.height} pixels, respectively.\n"
        prompt += (
            "To help you better perceive the content in these screenshots, we have extracted positional information for the text elements and icons. "
            "The format is: (coordinates; content). The coordinates are [x, y], where x represents the horizontal pixel position (from left to right) "
            "and y represents the vertical pixel position (from top to bottom).\n"
        )
        prompt += (
            "Note that these information might not be entirely accurate. "
            "You should combine them with the screenshots to gain a better understanding."
        )
        prompt += "\n\n"

        prompt += "### Screen Information Before the Action ###\n"
        for clickable_info in previous_screen_perception_info.perception_infos.infos:
            if clickable_info['text'] != "" and clickable_info['text'] != "icon: None" and clickable_info['coordinates'] != (0, 0):
                prompt += f"{clickable_info['coordinates']}; {clickable_info['text']}\n"
        prompt += "\n"
        prompt += "Keyboard status before the action: "
        if previous_screen_perception_info.perception_infos.keyboard_status:
            prompt += "The keyboard has been activated and you can type."
        else:
            prompt += "The keyboard has not been activated and you can\'t type."
        prompt += "\n\n"


        prompt += "### Screen Information After the Action ###\n"
        for clickable_info in current_screen_perception_info.perception_infos.infos:
            if clickable_info['text'] != "" and clickable_info['text'] != "icon: None" and clickable_info['coordinates'] != (0, 0):
                prompt += f"{clickable_info['coordinates']}; {clickable_info['text']}\n"
        prompt += "\n"
        prompt += "Keyboard status after the action: "
        if current_screen_perception_info.perception_infos.keyboard_status:
            prompt += "The keyboard has been activated and you can type."
        else:
            prompt += "The keyboard has not been activated and you can\'t type."
        prompt += "\n\n"

        prompt += "---\n"
        prompt += "### Latest Action ###\n"
        # assert message.last_action != ""
        prompt += f"Action: {action_info.action}\n"
        prompt += f"Expectation: {action_info.expectation}\n\n"

        prompt += "---\n"
        prompt += "Carefully examine the information provided above to determine whether the last action produced the expected behavior. If the action was successful, update the progress status accordingly. If the action failed, identify the failure mode and provide reasoning on the potential reason causing this failure. Note that for the “Swipe” action, it may take multiple attempts to display the expected content. Thus, for a \"Swipe\" action, if the screen shows new content, it usually meets the expectation.\n\n"

        prompt += "Provide your output in the following format containing three parts:\n\n"
        prompt += "### Outcome ###\n"
        prompt += "Choose from the following options."
        prompt += "A - explanation: Successful or Partially Successful. The result of the last action meets the expectation.\n"
        prompt += "B - explanation: Failed. The last action results in a wrong page. I need to return to the previous state.\n"
        prompt += "C - explanation: Failed. The last action produces no changes.\n\n"
        prompt += "Give your answer as \"A\", \"B\" or \"C\", DO NOT include explanations of options."

        prompt += "### Error Description ###\n"
        prompt += "If the action failed, provide a detailed description of the error and the potential reason causing this failure. If the action succeeded, put \"None\" here.\n\n"

        prompt += "### Progress Status ###\n"
        prompt += "If the action was successful or partially successful, update the progress status. If the action failed, copy the previous progress status.\n"

        return prompt

    def parse_response(self, response: str) -> ProgressInfo:
        outcome = (response.split("### Outcome ###")[-1].split("### Error Description ###")[0]
                   .replace("\n", " ").replace("  ", " ").strip())
        error_description = (response.split("### Error Description ###")[-1].split("### Progress Status ###")[0]
                             .replace("\n", " ").replace("  ", " ").strip())
        progress_status = (response.split("### Progress Status ###")[-1]
                           .replace("\n", " ").replace("  ", " ").strip())
        return ProgressInfo(outcome, error_description, progress_status)
