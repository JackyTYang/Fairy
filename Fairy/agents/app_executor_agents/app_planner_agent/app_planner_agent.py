import json
import re

from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.agents.app_executor_agents.app_planner_agent.planner_common import screen, plan_tips, plan_steps, \
    replan_output, plan_requirements
from Fairy.agents.prompt_common import ordered_list, output_json_object, unordered_list
from Fairy.config.fairy_config import FairyConfig
from Fairy.entity.info_entity import PlanInfo, ProgressInfo, ScreenInfo
from Fairy.entity.log_template import LogTemplate, WorkerType, LogEventType
from Fairy.memory.long_time_memory_manager import LongMemoryCallType, LongMemoryType
from Fairy.memory.short_time_memory_manager import ShortMemoryCallType, ActionMemoryType
from Fairy.entity.message_entity import EventMessage, CallMessage
from Fairy.entity.type import EventType, CallType, EventStatus, EventChannel


class AppPlannerAgent(Agent):
    def __init__(self, runtime, config: FairyConfig) -> None:
        system_messages = [ChatMessage(
            content="You are part of a helpful AI assistant for operating mobile phones and your identity is a planner. Your goal is to devise high-level plans to achieve the user's requests. Think as if you are a human user operating the phone, but if you are faced with uncertain options, you should actively interact with users.",
            type="SystemMessage")]
        super().__init__(runtime, "AppPlannerAgent", config.model_client, system_messages)
        self.log_t = LogTemplate(self)  # 日志模板

        self.non_visual_mode = config.non_visual_mode

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.match(EventType.ScreenPerception, EventStatus.DONE))
    async def on_plan(self, message: EventMessage, message_context):
        memory = await (await self.call("ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET, {
                ShortMemoryCallType.GET_Is_INIT_MODE: None
            })
        ))
        if memory[ShortMemoryCallType.GET_Is_INIT_MODE]:
            await self.do_plan_init(message, message_context)
        else:
            logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerSkip)("Init Plan", "NOT required for the non-first-time initialization"))

    async def do_plan_init(self, message: EventMessage, message_context):
        # 发布Plan CREATED事件 & 记录日志
        await self.publish(EventChannel.APP_CHANNEL, EventMessage(EventType.Plan, EventStatus.CREATED))
        logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerStart)("Init Plan"))

        # 从ShortTimeMemoryManager获取Instruction\Current Action Memory (StartScreenPerception)
        memory = await (await self.call("ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET, {
                ShortMemoryCallType.GET_Instruction:None,
                ShortMemoryCallType.GET_Current_Action_Memory:[ActionMemoryType.StartScreenPerception]
            })
        ))
        instruction_memory = memory[ShortMemoryCallType.GET_Instruction]
        current_action_memory = memory[ShortMemoryCallType.GET_Current_Action_Memory]

        # 从LongTimeMemoryManager获取Plan Tips
        long_memory = await (await self.call("LongTimeMemoryManager",
            CallMessage(CallType.Memory_GET,{
                LongMemoryCallType.GET_Tips: {
                    LongMemoryType.Plan_Tips: {"query": instruction_memory.get_instruction(), "app_package_name": instruction_memory.app_package_name}
                }
            })
        ))
        plan_tips = long_memory[LongMemoryCallType.GET_Tips][LongMemoryType.Plan_Tips]

        # 构建Prompt
        images = []
        if not self.non_visual_mode:
            images.append(current_action_memory[ActionMemoryType.StartScreenPerception].screenshot_file_info.get_screenshot_Image_file())

        plan_info = await self.request_llm(
            self.build_init_prompt(
                instruction_memory.get_instruction(),
                current_action_memory[ActionMemoryType.StartScreenPerception],
                plan_tips
            ),
            images=images
        )

        logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.IntermediateResult)("Init plan result", plan_info))

        # 发布Plan DONE事件 & 记录日志
        await self.publish(EventChannel.APP_CHANNEL, EventMessage(EventType.Plan, EventStatus.DONE, plan_info))
        logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerCompleted)("Init Plan"))

    def build_init_prompt(self, instruction, current_screen_perception_info: ScreenInfo, tips) -> str:
        prompt = f"---\n"\
                 f"- Instruction: {instruction}\n"\
                 f"\n"

        prompt += screen(current_screen_perception_info, self.non_visual_mode)

        prompt += f"---\n"\
                  f"Please follow these steps to develop a plan:\n"
        prompt += ordered_list(plan_steps)
        prompt += "\n"

        prompt += "Here's some REQUIREMENTS for developing the plan. These REQUIREMENTS are VERY IMPORTANT, so MAKE SURE you follow them to the letter:\n"
        prompt += unordered_list(plan_requirements)

        prompt += plan_tips(tips)

        prompt += output_json_object(replan_output)
        return prompt


    def parse_response(self, response: str) -> (PlanInfo, ProgressInfo):
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        response_jsonobject = json.loads(response)

        plan_info = PlanInfo(response_jsonobject['plan_thought'], response_jsonobject['overall_plan'], response_jsonobject['current_sub_goal'], 0, None)
        return plan_info
