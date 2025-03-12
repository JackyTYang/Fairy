from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage

class AppReflectorAgent(Agent):
    def __init__(self, runtime, model_client) -> None:
        super().__init__(runtime, "AppExecutorAgent", "AppExecutorAgent")
        self._system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to verify whether the last action produced the expected behavior and to keep track of the overall progress.",
            type="SystemMessage")]
        self._model_client = model_client

    @listener(ListenerType.ON_CALLED, listen_filter=lambda msg: True)
    async def on_called(self, message , message_context):
        content = self.build_prompt(message)
        user_message = ChatMessage(content=content, type="UserMessage", source="user")
        response = await self._model_client.create(
            self._system_messages + [user_message]
        )
        return self.parse_response(response.content)

    def build_prompt(self, message) -> str:
        prompt = "### User Instruction ###\n"
        prompt += f"{message.instruction}\n\n"

        prompt += "### Progress Status ###\n"
        if message.progress_status != "":
            prompt += f"{message.progress_status}\n\n"
        else:
            prompt += "No progress yet.\n\n"

        prompt += "### Current Subgoal ###\n"
        prompt += f"{message.current_subgoal}\n\n"

        prompt += "---\n"
        prompt += f"The attached two images are two phone screenshots before and after your last action. "
        prompt += f"The width and height are {message.width} and {message.height} pixels, respectively.\n"
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
        for clickable_info in message.perception_infos_pre:
            if clickable_info['text'] != "" and clickable_info['text'] != "icon: None" and clickable_info['coordinates'] != (0, 0):
                prompt += f"{clickable_info['coordinates']}; {clickable_info['text']}\n"
        prompt += "\n"
        prompt += "Keyboard status before the action: "
        if message.keyboard_pre:
            prompt += "The keyboard has been activated and you can type."
        else:
            prompt += "The keyboard has not been activated and you can\'t type."
        prompt += "\n\n"


        prompt += "### Screen Information After the Action ###\n"
        for clickable_info in message.perception_infos_post:
            if clickable_info['text'] != "" and clickable_info['text'] != "icon: None" and clickable_info['coordinates'] != (0, 0):
                prompt += f"{clickable_info['coordinates']}; {clickable_info['text']}\n"
        prompt += "\n"
        prompt += "Keyboard status after the action: "
        if message.keyboard_post:
            prompt += "The keyboard has been activated and you can type."
        else:
            prompt += "The keyboard has not been activated and you can\'t type."
        prompt += "\n\n"

        prompt += "---\n"
        prompt += "### Latest Action ###\n"
        # assert message.last_action != ""
        prompt += f"Action: {message.last_action}\n"
        prompt += f"Expectation: {message.last_summary}\n\n"

        prompt += "---\n"
        prompt += "Carefully examine the information provided above to determine whether the last action produced the expected behavior. If the action was successful, update the progress status accordingly. If the action failed, identify the failure mode and provide reasoning on the potential reason causing this failure. Note that for the “Swipe” action, it may take multiple attempts to display the expected content. Thus, for a \"Swipe\" action, if the screen shows new content, it usually meets the expectation.\n\n"

        prompt += "Provide your output in the following format containing three parts:\n\n"
        prompt += "### Outcome ###\n"
        prompt += "Choose from the following options. Give your answer as \"A\", \"B\" or \"C\":\n"
        prompt += "A: Successful or Partially Successful. The result of the last action meets the expectation.\n"
        prompt += "B: Failed. The last action results in a wrong page. I need to return to the previous state.\n"
        prompt += "C: Failed. The last action produces no changes.\n\n"

        prompt += "### Error Description ###\n"
        prompt += "If the action failed, provide a detailed description of the error and the potential reason causing this failure. If the action succeeded, put \"None\" here.\n\n"

        prompt += "### Progress Status ###\n"
        prompt += "If the action was successful or partially successful, update the progress status. If the action failed, copy the previous progress status.\n"

        return prompt

    def parse_response(self, response: str) -> dict:
        outcome = response.split("### Outcome ###")[-1].split("### Error Description ###")[0].replace("\n", " ").replace("  ", " ").strip()
        error_description = response.split("### Error Description ###")[-1].split("### Progress Status ###")[0].replace("\n", " ").replace("  ", " ").strip()
        progress_status = response.split("### Progress Status ###")[-1].replace("\n", " ").replace("  ", " ").strip()
        return {"outcome": outcome, "error_description": error_description, "progress_status": progress_status}
