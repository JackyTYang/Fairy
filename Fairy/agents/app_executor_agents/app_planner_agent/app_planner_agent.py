import json
import re

from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.agents.app_executor_agents.app_planner_agent.planner_common import screen, plan_tips, plan_steps, plan_output
from Fairy.agents.prompt_common import ordered_list, output_json_object
from Fairy.config.fairy_config import FairyConfig
from Fairy.info_entity import PlanInfo, ProgressInfo, ScreenInfo
from Fairy.memory.long_time_memory_manager import LongMemoryCallType
from Fairy.memory.short_time_memory_manager import ShortMemoryCallType, ActionMemoryType
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventType, EventStatus, CallType


class AppPlannerAgent(Agent):
    def __init__(self, runtime, config: FairyConfig) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to devise high-level plans to achieve the user's requests. Think as if you are a human user operating the phone, but if you are faced with uncertain options, you should actively interact with users.",
            type="SystemMessage")]
        super().__init__(runtime, "AppPlannerAgent", config.model_client, system_messages)
        self.non_visual_mode = config.non_visual_mode

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.ScreenPerception and msg.status == EventStatus.DONE)
    async def on_plan(self, message: EventMessage, message_context):
        memory = await (await self.call("ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET, {
                ShortMemoryCallType.GET_Is_INIT_MODE: None
            })
        ))
        if memory[ShortMemoryCallType.GET_Is_INIT_MODE]:
            await self.do_plan_init(message, message_context)
        else:
            logger.bind(log_tag="fairy_sys").warning("[Plan(INIT)] Plan already exists for task to be executed, skipped")

    async def do_plan_init(self, message: EventMessage, message_context):
        logger.bind(log_tag="fairy_sys").info("[Plan(INIT)] TASK in progress...")

        # 从ShortTimeMemoryManager获取Instruction\Current Action Memory (StartScreenPerception)
        memory = await (await self.call("ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET, {
                ShortMemoryCallType.GET_Instruction:None,
                ShortMemoryCallType.GET_Current_Action_Memory:[ActionMemoryType.StartScreenPerception]
            })
        ))
        instruction_memory = memory[ShortMemoryCallType.GET_Instruction]
        current_action_memory = memory[ShortMemoryCallType.GET_Current_Action_Memory]

        # 从LongTimeMemoryManager获取Tips
        long_memory = await (await self.call("LongTimeMemoryManager",
            CallMessage(CallType.Memory_GET,{
                LongMemoryCallType.GET_Plan_Tips: instruction_memory,
            })
        ))
        tips = long_memory[LongMemoryCallType.GET_Plan_Tips]

        # 构建Prompt
        images = []
        if not self.non_visual_mode:
            images.append(current_action_memory[ActionMemoryType.StartScreenPerception].screenshot_file_info.get_screenshot_Image_file())

        plan_event_content = await self.request_llm(
            self.build_init_prompt(
                instruction_memory,
                current_action_memory[ActionMemoryType.StartScreenPerception],
                tips
            ),
            images=images
        )
        # 发布Plan事件
        await self.publish("app_channel", EventMessage(EventType.Plan, EventStatus.DONE, plan_event_content))
        logger.bind(log_tag="fairy_sys").info("[Plan(INIT)] TASK completed.")


    def build_init_prompt(self, instruction, current_screen_perception_info: ScreenInfo, tips) -> str:
        prompt = f"---\n"\
                 f"- Instruction: {instruction}\n"\
                 f"\n"

        prompt += screen(current_screen_perception_info, self.non_visual_mode)

        prompt += f"---\n"\
                  f"Please follow these steps to develop a plan:\n"
        prompt += ordered_list(plan_steps)
        prompt += "\n"

        prompt += plan_tips(tips)

        prompt += output_json_object(plan_output)
        return prompt


    def parse_response(self, response: str) -> (PlanInfo, ProgressInfo):
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        response_jsonobject = json.loads(response)

        plan_info = PlanInfo(response_jsonobject['plan_thought'], response_jsonobject['overall_plan'], response_jsonobject['current_sub_goal'], 0, None)
        return plan_info
