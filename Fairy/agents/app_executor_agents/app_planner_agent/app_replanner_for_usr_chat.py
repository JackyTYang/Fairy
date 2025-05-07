import json
import re

from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.agents.app_executor_agents.app_planner_agent.planner_common import \
    replan_output_for_usr_chat, screen, replan_steps_for_usr_chat
from Fairy.agents.prompt_common import output_json_object, ordered_list
from Fairy.config.fairy_config import FairyConfig
from Fairy.info_entity import PlanInfo, ProgressInfo, ScreenInfo, UserInteractionInfo
from Fairy.memory.short_time_memory_manager import ShortMemoryCallType, ActionMemoryType
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventType, CallType


class AppRePlannerForUsrChatAgent(Agent):
    def __init__(self, runtime, config: FairyConfig) -> None:
        system_messages = [ChatMessage(
            content="You are part of a helpful AI assistant for operating mobile phones and your identity is a planner. Your goal is to verify whether the last action produced the expected behavior, to keep track of the progress and devise high-level plans to achieve the user's requests.",
            type="SystemMessage")]
        super().__init__(runtime, "RePlannerForUsrChat", config.model_client, system_messages)

        self.instruction_tips = None
        self.non_visual_mode = config.non_visual_mode

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.UserInteraction_DONE)
    async def on_plan_after_user_interaction(self, message: EventMessage, message_context):
        logger.bind(log_tag="fairy_sys").info("[Plan(UserInteraction)] TASK in progress...")
        # 从ShortTimeMemoryManager获取Instruction\Current Action Memory (Plan, StartScreenPerception)
        memory = await (await self.call(
            "ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET, {
                ShortMemoryCallType.GET_Instruction:None,
                ShortMemoryCallType.GET_Current_Action_Memory:[ActionMemoryType.Plan, ActionMemoryType.StartScreenPerception],
                ShortMemoryCallType.GET_Key_Info:None
            })
        ))
        instruction_memory = memory[ShortMemoryCallType.GET_Instruction]
        current_action_memory = memory[ShortMemoryCallType.GET_Current_Action_Memory]

        # 构建Prompt
        images = []
        if not self.non_visual_mode:
            images.append(current_action_memory[ActionMemoryType.StartScreenPerception].screenshot_file_info.get_screenshot_Image_file())

        plan_event_content = await self.request_llm(
            self.build_after_user_interaction_prompt(
                instruction_memory.get_instruction(),
                current_action_memory[ActionMemoryType.Plan],
                message.event_content,
                current_action_memory[ActionMemoryType.StartScreenPerception],
            ),
            images=images
        )
        await self.publish("app_channel", EventMessage(EventType.Plan_DONE, plan_event_content))
        logger.bind(log_tag="fairy_sys").info("[Plan(UserInteraction)] TASK completed.")

    def build_after_user_interaction_prompt(self,
                                            instruction,
                                            plan_info: PlanInfo,
                                            user_interaction_info: UserInteractionInfo,
                                            current_screen_perception_info: ScreenInfo,
                                            ) -> str:
        prompt = f"---\n"\
                 f"The User Interactor Agent has just finished interacting with the user as you had previously planned, and this is the user interaction type and result:\n"\
                 f"- User Interaction Type: {plan_info.user_interaction_type}\n"\
                 f"- User Response: {user_interaction_info.response}\n"\
                 f"\n"

        prompt += f"---\n"\
                  f"This is the overall plan, sub-goal, and thought that was executed prior to the interaction:"\
                  f"- Overall Plan: {plan_info.overall_plan}\n" \
                  f"- Sub-goal: {plan_info.current_sub_goal}\n" \
                  f"- Plan Thought: {plan_info.plan_thought}\n" \
                  f"\n" \

        prompt += f"The Instruction has been updated to: {instruction}\n"\
                  f"\n"

        prompt += screen(current_screen_perception_info, self.non_visual_mode)

        prompt += f"---\n"\
                  f"Please follow the steps below to perform the action:\n"
        prompt += ordered_list(replan_steps_for_usr_chat)

        prompt += output_json_object(replan_output_for_usr_chat)
        return prompt

    def parse_response(self, response: str) -> (PlanInfo, ProgressInfo):
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        response_jsonobject = json.loads(response)

        plan_info = PlanInfo(response_jsonobject['plan_thought'], response_jsonobject['overall_plan'], response_jsonobject['current_sub_goal'], response_jsonobject['user_interaction_type'], response_jsonobject['user_interaction_thought'])
        return plan_info