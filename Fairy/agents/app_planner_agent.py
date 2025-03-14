from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.info_entity import PlanInfo, ProgressInfo
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventType, EventStatus, CallType, MemoryType


class AppPlannerAgent(Agent):
    def __init__(self, runtime, model_client) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to track progress and devise high-level plans to achieve the user's requests. Think as if you are a human user operating the phone.",
            type="SystemMessage")]
        super().__init__(runtime, "AppPlannerAgent", model_client, system_messages)

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.Plan and msg.status == EventStatus.CREATED)
    async def on_plan_init(self, message: EventMessage, message_context):
        logger.debug("Plan(First Run) task in progress...")

        instruction = message.event_content
        # 从ShortTimeMemoryManager获取CurrentScreenPerception
        memory = await self.call("ShortTimeMemoryManager", CallMessage(CallType.Memory_GET, [MemoryType.ScreenPerception]))
        memory = await memory
        # 构建Prompt
        event_content = await self.request_llm(
            self.build_init_prompt(instruction),
            [
                memory[MemoryType.ScreenPerception][-1].screenshot_file_info.get_screenshot_Image_file(), # CurrentScreenImageFile
            ]
        )
        # 发布Plan事件
        await self.publish("app_channel", EventMessage(EventType.Plan, EventStatus.DONE, event_content))

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.Reflection and msg.status == EventStatus.DONE)
    async def on_plan_next(self, message:EventMessage , message_context):

        logger.debug("Plan task in progress...")

        # 从ShortTimeMemoryManager获取Instruction, CurrentScreenPerception, Plan
        memory = await self.call("ShortTimeMemoryManager", CallMessage(CallType.Memory_GET, [MemoryType.Instruction, MemoryType.ScreenPerception, MemoryType.Plan]))
        memory = await memory
        # 构建Prompt
        event_content = await self.request_llm(
            self.build_prompt(
                memory[MemoryType.Instruction], # Instruction
                memory[MemoryType.Plan][-1], # PlanInfo
                message.event_content # ProgressInfo
            ),
            [
                memory[MemoryType.ScreenPerception][-1].screenshot_file_info.get_screenshot_Image_file(), # CurrentScreenImageFile
            ]
        )
        # 发布Plan事件
        await self.publish("app_channel", EventMessage(EventType.Plan, EventStatus.DONE, event_content))

    @staticmethod
    def build_init_prompt(instruction) -> str:
        prompt = "### User Instruction ###\n"
        prompt += f"{instruction}\n\n"
        # first time planning
        prompt += "---\n"
        prompt += "Think step by step and make an high-level plan to achieve the user's instruction. If the request is complex, break it down into subgoals. If the request involves exploration, include concrete subgoals to quantify the investigation steps. The screenshot displays the starting state of the phone.\n\n"

        prompt += "Provide your output in the following format which contains three parts:\n\n"
        prompt += "### Thought ###\n"
        prompt += "A detailed explanation of your rationale for the plan and subgoals.\n\n"
        prompt += "### Plan ###\n"
        prompt += "1. first subgoal\n"
        prompt += "2. second subgoal\n"
        prompt += "...\n\n"
        prompt += "### Current Subgoal ###\n"
        prompt += "The first subgoal you should work on.\n\n"
        return prompt

    @staticmethod
    def build_prompt(instruction, plan_info:PlanInfo, progress_info:ProgressInfo) -> str:
        prompt = "### User Instruction ###\n"
        prompt += f"{instruction}\n\n"

        # continue planning
        prompt += "### Current Plan ###\n"
        prompt += f"{plan_info.plan}\n\n"
        prompt += "### Previous Subgoal ###\n"
        prompt += f"{plan_info.current_sub_goal}\n\n"
        prompt += f"### Progress Status ###\n"
        prompt += f"{progress_info.progress_status}\n\n"

        # if message.error_flag_plan:
        #     prompt += "### Potentially Stuck! ###\n"
        #     prompt += "You have encountered several failed attempts. Here are some logs:\n"
        #     k = message.err_to_manager_thresh
        #     recent_actions = message.action_history[-k:]
        #     recent_summaries = message.summary_history[-k:]
        #     recent_err_des = message.error_descriptions[-k:]
        #     for i, (act, summ, err_des) in enumerate(zip(recent_actions, recent_summaries, recent_err_des)):
        #         prompt += f"- Attempt: Action: {act} | Description: {summ} | Outcome: Failed | Feedback: {err_des}\n"

        prompt += "---\n"
        prompt += "The sections above provide an overview of the plan you are following, the current subgoal you are working on, the overall progress made, and any important notes you have recorded. The screenshot displays the current state of the phone.\n"
        prompt += "Carefully assess the current status to determine if the task has been fully completed. If the user's request involves exploration, ensure you have conducted sufficient investigation. If you are confident that no further actions are required, mark the task as \"Finished\" in your output. If the task is not finished, outline the next steps. If you are stuck with errors, think step by step about whether the overall plan needs to be revised to address the error.\n"
        prompt += "NOTE: If the current situation prevents proceeding with the original plan or requires clarification from the user, make reasonable assumptions and revise the plan accordingly. Act as though you are the user in such cases.\n\n"

        prompt += "---\n"
        prompt += "Provide your output in the following format, which contains three parts:\n\n"
        prompt += "### Thought ###\n"
        prompt += "Provide a detailed explanation of your rationale for the plan and subgoals.\n\n"
        prompt += "### Plan ###\n"
        prompt += "If an update is required for the high-level plan, provide the updated plan here. Otherwise, keep the current plan and copy it here.\n\n"
        prompt += "### Current Subgoal ###\n"
        prompt += "The next subgoal to work on. If the previous subgoal is not yet complete, copy it here. If all subgoals are completed, write \"Finished\".\n"
        return prompt

    def parse_response(self, response: str) -> PlanInfo:
        thought = (response.split("### Thought ###")[-1].split("### Plan ###")[0]
                   .replace("\n", " ").replace("  "," ").strip())
        plan = (response.split("### Plan ###")[-1].split("### Current Subgoal ###")[0]
                .replace("\n", " ").replace("  "," ").strip())
        current_sub_goal = (response.split("### Current Subgoal ###")[-1]
                           .replace("\n", " ").replace("  ", " ").strip())
        return PlanInfo(thought, plan, current_sub_goal)
