import json
import re

from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.agents.app_executor_agents.app_planner_agent.reflector_common import old_and_new_screen_comparison, reflection_steps, \
    reflection_output, is_finished_action
from Fairy.agents.prompt_common import output_json_object, ordered_list
from Fairy.config.fairy_config import FairyConfig
from Fairy.entity.info_entity import PlanInfo, ProgressInfo, ScreenInfo, ActionInfo
from Fairy.entity.log_template import WorkerType, LogTemplate
from Fairy.memory.short_time_memory_manager import ShortMemoryCallType, ActionMemoryType
from Fairy.entity.message_entity import EventMessage, CallMessage
from Fairy.entity.type import EventType, CallType, EventChannel, EventStatus


class AppReflectorAgent(Agent):
    def __init__(self, runtime, config: FairyConfig) -> None:
        system_messages = [ChatMessage(
            content="You are part of a helpful AI assistant for operating mobile phones and your identity is a reflector. Your goal is to verify whether the last action produced the expected behavior, to keep track of the progress.",
            type="SystemMessage")]
        super().__init__(runtime, "AppReflectorAgent", config.model_client, system_messages)

        self.non_visual_mode = config.non_visual_mode
        self.standalone_reflector_mode = config.reflection_policy == "standalone"
        if self.standalone_reflector_mode:
            logger.bind(log_tag="fairy_sys").warning(
                "WARNING: Standalone Reflector mode has been activated, in which the reflector and replanner will be executed separately, which may result in a slowdown. You can switch to hybrid mode by configuring the 'reflection_policy' setting in FairyConfig to 'hybrid'.")

    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.APP_CHANNEL,
              listen_filter=lambda msg: msg.match(EventType.ScreenPerception, EventStatus.DONE))
    async def on_reflect(self, message: EventMessage, message_context):
        if not self.standalone_reflector_mode:
            logger.bind(log_tag="fairy_sys").warning(LogTemplate["worker_skip"](WorkerType.Agent, self.name, "Configuration item 'selection_policy' is 'hybrid' mode"))
            return

        memory = await (await self.call("ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET, {
                ShortMemoryCallType.GET_Is_INIT_MODE: None
            })
        ))
        if memory[ShortMemoryCallType.GET_Is_INIT_MODE]:
            logger.bind(log_tag="fairy_sys").warning(LogTemplate["worker_skip"](WorkerType.Agent, self.name, "NOT required for the first initialization"))
            return
        else:
            await self.do_reflect(message, message_context)

    async def do_reflect(self, message: EventMessage, message_context):
        # 发布Reflection CREATED事件 & 记录日志
        await self.publish(EventChannel.APP_CHANNEL, EventMessage(EventType.Reflection, EventStatus.CREATED))
        logger.bind(log_tag="fairy_sys").info(LogTemplate['worker_start'](WorkerType.Agent, self.name))

        # 从ShortTimeMemoryManager获取Instruction\Current Action Memory (Plan, Action, StartScreenPerception, EndScreenPerception)\KeyInfo
        memory = await (await self.call(
            "ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET, {
                ShortMemoryCallType.GET_Instruction:None,
                ShortMemoryCallType.GET_Current_Action_Memory:[ActionMemoryType.Plan, ActionMemoryType.Action, ActionMemoryType.StartScreenPerception, ActionMemoryType.EndScreenPerception],
                ShortMemoryCallType.GET_Key_Info:None
            })
        ))
        instruction_memory = memory[ShortMemoryCallType.GET_Instruction]
        current_action_memory = memory[ShortMemoryCallType.GET_Current_Action_Memory]
        key_info_memory = memory[ShortMemoryCallType.GET_Key_Info]

        # 构建Prompt
        images = []
        if not self.non_visual_mode:
            images.append(current_action_memory[ActionMemoryType.StartScreenPerception].screenshot_file_info.get_screenshot_Image_file())
            images.append(current_action_memory[ActionMemoryType.EndScreenPerception].screenshot_file_info.get_screenshot_Image_file())

        reflection_event_content = await self.request_llm(
            self.build_prompt(
                instruction_memory.get_instruction(),
                current_action_memory[ActionMemoryType.Plan],
                current_action_memory[ActionMemoryType.Action],
                current_action_memory[ActionMemoryType.StartScreenPerception],
                current_action_memory[ActionMemoryType.EndScreenPerception],
                key_info_memory
            ),
            images=images
        )

        if is_finished_action(reflection_event_content, current_action_memory[ActionMemoryType.Action]):
            # 发布Task DONE事件 & 记录日志
            await self.publish(EventChannel.APP_CHANNEL, EventMessage(EventType.Task, EventStatus.DONE))
            logger.bind(log_tag="fairy_sys").info(LogTemplate['task_complete']())
        else:
            # 发布Reflection DONE事件 & 记录日志
            await self.publish(EventChannel.APP_CHANNEL, EventMessage(EventType.Reflection, EventStatus.DONE, reflection_event_content))
            logger.bind(log_tag="fairy_sys").info(LogTemplate['worker_complete'](WorkerType.Agent, self.name))

    def build_prompt(self,
                     instruction,
                     plan_info: PlanInfo,
                     action_info: ActionInfo,
                     previous_screen_perception_info: ScreenInfo,
                     current_screen_perception_info: ScreenInfo,
                     key_infos: list) -> str:
        prompt = f"---\n"\
                 f"The Executor Agent has just finished executing according to your previous plan, which is the sub-goal, action, and expected results of this execution:\n"\
                 f"- Sub-goal: {plan_info.current_sub_goal}\n"\
                 f"- Action(s): {action_info.actions}\n"\
                 f"- Action Expectation: {action_info.action_expectation}\n"\
                 f"\n"

        prompt += old_and_new_screen_comparison(previous_screen_perception_info, current_screen_perception_info, self.non_visual_mode)

        prompt += f"---\n"\
                  f"- Instruction: {instruction}\n"\
                  f"- Overall Plan: {plan_info.overall_plan}\n"\
                  f"- Key Information Record (Excluding Current Screen): {key_infos}\n" \
                  f"\n"

        prompt += f"---\n"\
                  f"Please follow these steps to check the progress of sub-goal completion:\n"
        prompt += ordered_list(reflection_steps)
        prompt += "\n"

        prompt += output_json_object(reflection_output)

        return prompt

    def parse_response(self, response: str) -> (PlanInfo, ProgressInfo):
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        response_jsonobject = json.loads(response)

        progress_info = ProgressInfo(response_jsonobject['action_result'], response_jsonobject['error_potential_causes'],
                response_jsonobject['progress_status'])

        return progress_info