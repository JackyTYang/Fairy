from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage


class AppPlannerAgent(Agent):
    def __init__(self, runtime, model_client) -> None:
        super().__init__(runtime, "AppPlannerAgent", "AppPlannerAgent")
        self._system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to track progress and devise high-level plans to achieve the user's requests. Think as if you are a human user operating the phone.",
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

        if message.plan == "":
            # first time planning
            prompt += "---\n"
            prompt += "Think step by step and make an high-level plan to achieve the user's instruction. If the request is complex, break it down into subgoals. If the request involves exploration, include concrete subgoals to quantify the investigation steps. The screenshot displays the starting state of the phone.\n\n"

            if message.shortcuts != {}:
                prompt += "### Available Shortcuts from Past Experience ###\n"
                prompt += "We additionally provide some shortcut functionalities based on past experience. These shortcuts are predefined sequences of operations that might make the plan more efficient. Each shortcut includes a precondition specifying when it is suitable for use. If your plan implies the use of certain shortcuts, ensure that the precondition is fulfilled before using them. Note that you don't necessarily need to include the names of these shortcuts in your high-level plan; they are provided as a reference.\n"
                for shortcut, value in message.shortcuts.items():
                    prompt += f"- {shortcut}: {value['description']} | Precondition: {value['precondition']}\n"
                prompt += "\n"
            prompt += "---\n"

            prompt += "Provide your output in the following format which contains three parts:\n\n"
            prompt += "### Thought ###\n"
            prompt += "A detailed explanation of your rationale for the plan and subgoals.\n\n"
            prompt += "### Plan ###\n"
            prompt += "1. first subgoal\n"
            prompt += "2. second subgoal\n"
            prompt += "...\n\n"
            prompt += "### Current Subgoal ###\n"
            prompt += "The first subgoal you should work on.\n\n"
        else:
            # continue planning
            prompt += "### Current Plan ###\n"
            prompt += f"{message.plan}\n\n"
            prompt += "### Previous Subgoal ###\n"
            prompt += f"{message.current_subgoal}\n\n"
            prompt += f"### Progress Status ###\n"
            prompt += f"{message.progress_status}\n\n"
            prompt += "### Important Notes ###\n"
            if message.important_notes != "":
                prompt += f"{message.important_notes}\n\n"
            else:
                prompt += "No important notes recorded.\n\n"
            if message.error_flag_plan:
                prompt += "### Potentially Stuck! ###\n"
                prompt += "You have encountered several failed attempts. Here are some logs:\n"
                k = message.err_to_manager_thresh
                recent_actions = message.action_history[-k:]
                recent_summaries = message.summary_history[-k:]
                recent_err_des = message.error_descriptions[-k:]
                for i, (act, summ, err_des) in enumerate(zip(recent_actions, recent_summaries, recent_err_des)):
                    prompt += f"- Attempt: Action: {act} | Description: {summ} | Outcome: Failed | Feedback: {err_des}\n"

            prompt += "---\n"
            prompt += "The sections above provide an overview of the plan you are following, the current subgoal you are working on, the overall progress made, and any important notes you have recorded. The screenshot displays the current state of the phone.\n"
            prompt += "Carefully assess the current status to determine if the task has been fully completed. If the user's request involves exploration, ensure you have conducted sufficient investigation. If you are confident that no further actions are required, mark the task as \"Finished\" in your output. If the task is not finished, outline the next steps. If you are stuck with errors, think step by step about whether the overall plan needs to be revised to address the error.\n"
            prompt += "NOTE: If the current situation prevents proceeding with the original plan or requires clarification from the user, make reasonable assumptions and revise the plan accordingly. Act as though you are the user in such cases.\n\n"

            if message.shortcuts != {}:
                prompt += "### Available Shortcuts from Past Experience ###\n"
                prompt += "We additionally provide some shortcut functionalities based on past experience. These shortcuts are predefined sequences of operations that might make the plan more efficient. Each shortcut includes a precondition specifying when it is suitable for use. If your plan implies the use of certain shortcuts, ensure that the precondition is fulfilled before using them. Note that you don't necessarily need to include the names of these shortcuts in your high-level plan; they are provided only as a reference.\n"
                for shortcut, value in message.shortcuts.items():
                    prompt += f"- {shortcut}: {value['description']} | Precondition: {value['precondition']}\n"
                prompt += "\n"

            prompt += "---\n"
            prompt += "Provide your output in the following format, which contains three parts:\n\n"
            prompt += "### Thought ###\n"
            prompt += "Provide a detailed explanation of your rationale for the plan and subgoals.\n\n"
            prompt += "### Plan ###\n"
            prompt += "If an update is required for the high-level plan, provide the updated plan here. Otherwise, keep the current plan and copy it here.\n\n"
            prompt += "### Current Subgoal ###\n"
            prompt += "The next subgoal to work on. If the previous subgoal is not yet complete, copy it here. If all subgoals are completed, write \"Finished\".\n"
        return prompt

    def parse_response(self, response: str) -> dict:
        thought = response.split("### Thought ###")[-1].split("### Plan ###")[0].replace("\n", " ").replace("  ",
                                                                                                            " ").strip()
        plan = response.split("### Plan ###")[-1].split("### Current Subgoal ###")[0].replace("\n", " ").replace("  ",
                                                                                                                 " ").strip()
        current_subgoal = response.split("### Current Subgoal ###")[-1].replace("\n", " ").replace("  ", " ").strip()
        return {"thought": thought, "plan": plan, "current_subgoal": current_subgoal}
