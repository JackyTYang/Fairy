from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.tools.type import ATOMIC_ACTION_SIGNITURES


def extract_json_object(action_str):
    pass


class AppExecutorAgent(Agent):
    def __init__(self, runtime, model_client) -> None:
        super().__init__(runtime, "AppExecutorAgent", "AppExecutorAgent")
        self._system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to choose the correct actions to complete the user's instruction. Think as if you are a human user operating the phone.",
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

        prompt += "### Overall Plan ###\n"
        prompt += f"{message.plan}\n\n"

        prompt += "### Progress Status ###\n"
        if message.progress_status != "":
            prompt += f"{message.progress_status}\n\n"
        else:
            prompt += "No progress yet.\n\n"

        prompt += "### Current Subgoal ###\n"
        prompt += f"{message.current_subgoal}\n\n"

        prompt += "### Screen Information ###\n"
        prompt += (
            f"The attached image is a screenshot showing the current state of the phone. "
            f"Its width and height are {message.width} and {message.height} pixels, respectively.\n"
        )
        prompt += (
            "To help you better understand the content in this screenshot, we have extracted positional information for the text elements and icons, including interactive elements such as search bars. "
            "The format is: (coordinates; content). The coordinates are [x, y], where x represents the horizontal pixel position (from left to right) "
            "and y represents the vertical pixel position (from top to bottom)."
        )
        prompt += "The extracted information is as follows:\n"

        for clickable_info in message.perception_infos_pre:
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
        if message.keyboard_pre:
            prompt += "The keyboard has been activated and you can type."
        else:
            prompt += "The keyboard has not been activated and you can\'t type."
        prompt += "\n\n"

        if message.tips != "":
            prompt += "### Tips ###\n"
            prompt += "From previous experience interacting with the device, you have collected the following tips that might be useful for deciding what to do next:\n"
            prompt += f"{message.tips}\n\n"

        prompt += "### Important Notes ###\n"
        if message.important_notes != "":
            prompt += "Here are some potentially important content relevant to the user's request you already recorded:\n"
            prompt += f"{message.important_notes}\n\n"
        else:
            prompt += "No important notes recorded.\n\n"

        prompt += "---\n"
        prompt += "Carefully examine all the information provided above and decide on the next action to perform. If you notice an unsolved error in the previous action, think as a human user and attempt to rectify them. You must choose your action from one of the atomic actions or the shortcuts. The shortcuts are predefined sequences of actions that can be used to speed up the process. Each shortcut has a precondition specifying when it is suitable to use. If you plan to use a shortcut, ensure the current phone state satisfies its precondition first.\n\n"

        prompt += "#### Atomic Actions ####\n"
        prompt += "The atomic action functions are listed in the format of `name(arguments): description` as follows:\n"

        if message.keyboard_pre:
            for action, value in ATOMIC_ACTION_SIGNITURES.items():
                prompt += f"- {action}({', '.join(value['arguments'])}): {value['description'](message)}\n"
        else:
            for action, value in ATOMIC_ACTION_SIGNITURES.items():
                if "Type" not in action:
                    prompt += f"- {action}({', '.join(value['arguments'])}): {value['description'](message)}\n"
            prompt += "NOTE: Unable to type. The keyboard has not been activated. To type, please activate the keyboard by tapping on an input box or using a shortcut, which includes tapping on an input box first.”\n"

        prompt += "\n"
        prompt += "#### Shortcuts ####\n"
        if message.shortcuts != {}:
            prompt += "The shortcut functions are listed in the format of `name(arguments): description | Precondition: precondition` as follows:\n"
            for shortcut, value in message.shortcuts.items():
                prompt += f"- {shortcut}({', '.join(value['arguments'])}): {value['description']} | Precondition: {value['precondition']}\n"
        else:
            prompt += "No shortcuts are available.\n"
        prompt += "\n"

        prompt += "### Latest Action History ###\n"
        if message.action_history != []:
            prompt += "Recent actions you took previously and whether they were successful:\n"
            num_actions = min(5, len(message.action_history))
            latest_actions = message.action_history[-num_actions:]
            latest_summary = message.summary_history[-num_actions:]
            latest_outcomes = message.action_outcomes[-num_actions:]
            error_descriptions = message.error_descriptions[-num_actions:]
            action_log_strs = []
            for act, summ, outcome, err_des in zip(latest_actions, latest_summary, latest_outcomes, error_descriptions):
                if outcome == "A":
                    action_log_str = f"Action: {act} | Description: {summ} | Outcome: Successful\n"
                else:
                    action_log_str = f"Action: {act} | Description: {summ} | Outcome: Failed | Feedback: {err_des}\n"
                prompt += action_log_str
                action_log_strs.append(action_log_str)
            if latest_outcomes[-1] == "C" and "Tap" in action_log_strs[-1] and "Tap" in action_log_strs[-2]:
                prompt += "\nHINT: If multiple Tap actions failed to make changes to the screen, consider using a \"Swipe\" action to view more content or use another way to achieve the current subgoal."

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
        prompt += "You must provide your decision using a valid JSON format specifying the name and arguments of the action. For example, if you choose to tap at position (100, 200), you should write {\"name\":\"Tap\", \"arguments\":{\"x\":100, \"y\":100}}. If an action does not require arguments, such as Home, fill in null to the \"arguments\" field. Ensure that the argument keys match the action function's signature exactly.\n\n"

        prompt += "### Description ###\n"
        prompt += "A brief description of the chosen action and the expected outcome."
        return prompt

    def execute(self, action_str: str, message, screenshot_log_dir=None, iter="", **kwargs) -> None:
        action_object = extract_json_object(action_str)
        if action_object is None:
            print("Error! Invalid JSON for executing action: ", action_str)
            return None, 0, None
        action, arguments = action_object["name"], action_object["arguments"]
        action = action.strip()

        # execute atomic action
        if action in ATOMIC_ACTION_SIGNITURES:
            print("Executing atomic action: ", action, arguments)

        else:
            if action.lower() in ["null", "none", "finish", "exit", "stop"]:
                print("Agent choose to finish the task. Action: ", action)
            else:
                print("Error! Invalid action name: ", action)
            message.finish_thought = message.last_action_thought
            return None, 0, None

    def parse_response(self, response: str) -> dict:
        thought = response.split("### Thought ###")[-1].split("### Action ###")[0].replace("\n", " ").replace("  ",
                                                                                                              " ").strip()
        action = response.split("### Action ###")[-1].split("### Description ###")[0].replace("\n", " ").replace("  ",
                                                                                                                 " ").strip()
        description = response.split("### Description ###")[-1].replace("\n", " ").replace("  ", " ").strip()
        return {"thought": thought, "action": action, "description": description}