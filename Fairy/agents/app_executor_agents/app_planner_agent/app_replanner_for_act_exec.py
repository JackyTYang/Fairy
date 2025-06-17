import asyncio
import json
import re

from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.agents.app_executor_agents.app_planner_agent.reflector_common import old_and_new_screen_comparison, reflection_steps, \
    reflection_output, is_finished_action

from Fairy.agents.app_executor_agents.app_planner_agent.planner_common import replan_output, plan_tips, plan_steps, \
    plan_requirements
from Fairy.agents.app_executor_agents.app_planner_agent.planner_common import screen, replan_steps
from Fairy.agents.prompt_common import ordered_list, output_json_object, unordered_list
from Fairy.config.fairy_config import FairyConfig
from Fairy.info_entity import PlanInfo, ProgressInfo, ScreenInfo, ActionInfo
from Fairy.memory.long_time_memory_manager import LongMemoryCallType, LongMemoryType
from Fairy.memory.short_time_memory_manager import ShortMemoryCallType, ActionMemoryType
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventType, CallType


class AppRePlannerForActExecAgent(Agent):
    def __init__(self, runtime, config: FairyConfig) -> None:
        system_messages = [ChatMessage(
            content="You are part of a helpful AI assistant for operating mobile phones and your identity is a planner. Your step is to verify whether the last action produced the expected behavior, to keep track of the progress and devise high-level plans to achieve the user's requests. Think as if you are a human user operating the phone, but if you are faced with uncertain options, you should actively interact with users.",
            type="SystemMessage")]
        super().__init__(runtime, "AppRePlannerForActExecAgent", config.model_client, system_messages)


        self.non_visual_mode = config.non_visual_mode
        self.standalone_reflector_mode = config.reflection_policy == "standalone"
        self.tag = "[Plan (Standalone Reflector Mode)]" if self.standalone_reflector_mode else "[RePlan (Hybrid Reflector Mode)]"

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.ScreenPerception_DONE)
    async def on_plan_with_hybrid_reflector_mode(self, message: EventMessage, message_context):
        if self.standalone_reflector_mode:
            logger.bind(log_tag="fairy_sys").warning("[Plan (Hybrid Reflector Mode)] Configuration item 'selection_policy' is 'standalone' mode, skipped")
            return
        else:
            await self.do_plan(message, message_context)

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.Reflection_DONE)
    async def on_plan_with_standalone_reflector_mode(self, message: EventMessage, message_context):
        if self.standalone_reflector_mode:
            await self.do_plan(message, message_context)
        else:
            logger.bind(log_tag="fairy_sys").warning("[RePlan (Standalone Reflector Mode)] Configuration item 'selection_policy' is 'hybrid' mode, skipped")
            return


    async def do_plan(self, message: EventMessage, message_context):
        memory = await (await self.call(
            "ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET, {
                ShortMemoryCallType.GET_Is_INIT_MODE: None
            })
        ))
        if memory[ShortMemoryCallType.GET_Is_INIT_MODE]:
            logger.bind(log_tag="fairy_sys").warning(f"{self.tag} Tasks do not have an executing plan and require an initial plan, skipped")
            return
        else:
            await self.on_replan_for_act_exec(message, message_context)


    async def on_replan_for_act_exec(self, message: EventMessage, message_context):
        logger.bind(log_tag="fairy_sys").info(f"{self.tag} TASK in progress...")

        if not self.standalone_reflector_mode:
            logger.bind(log_tag="fairy_sys").warning(
                f"{self.tag} WARNING: “The 'reflection-Planning' hybrid mode (RePlan Mode) has been activated, in which the reflector and planner will be mixed, which, although speeding things up, may lead to incorrect conclusions in specific models where the context is too large. You can switch the mode by configuring the 'reflection_policy' setting in FairyConfig to 'standalone'.")

        # 从ShortTimeMemoryManager获取Instruction\KeyInfo\Action Memory
        memory_get_call_content = {
                ShortMemoryCallType.GET_Instruction:None,
                ShortMemoryCallType.GET_Key_Info:None
            }
        if not self.standalone_reflector_mode:
            memory_get_call_content[ShortMemoryCallType.GET_Current_Action_Memory] = [
                ActionMemoryType.Plan, ActionMemoryType.Action,
                ActionMemoryType.StartScreenPerception, ActionMemoryType.EndScreenPerception
            ]
            # 取出当前的Plan, Action, StartScreenPerception, EndScreenPerception
        else:
            memory_get_call_content[ShortMemoryCallType.GET_Current_Action_Memory] = [
                ActionMemoryType.Plan, ActionMemoryType.Action,
                ActionMemoryType.ActionResult, ActionMemoryType.EndScreenPerception
            ]
            # 取出当前的Plan, Action, ActionResult, EndScreenPerception

        memory = await (await self.call(
            "ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET, memory_get_call_content)
        ))
        instruction_memory = memory[ShortMemoryCallType.GET_Instruction]
        key_info_memory = memory[ShortMemoryCallType.GET_Key_Info]
        current_action_memory = memory[ShortMemoryCallType.GET_Current_Action_Memory]

        # 如果是standalone_reflector_mode，检查任务是否已经结束
        if self.standalone_reflector_mode:
            if is_finished_action(current_action_memory[ActionMemoryType.ActionResult], current_action_memory[ActionMemoryType.Action]):
                logger.bind(log_tag="fairy_sys").warning(f"{self.tag} The action has not been completed yet, skipped")
                return

        # 从LongTimeMemoryManager获取Tips
        long_memory = await (await self.call("LongTimeMemoryManager",
            CallMessage(CallType.Memory_GET,{
                LongMemoryCallType.GET_Tips: {
                    LongMemoryType.Plan_Tips: {"query": instruction_memory, "app_package_name": instruction_memory.app_package_name}
                }
            })
        ))
        plan_tips = long_memory[LongMemoryCallType.GET_Tips][LongMemoryType.Plan_Tips]

        # 构建Prompt
        images = []
        if not self.non_visual_mode:
            images.append(current_action_memory[ActionMemoryType.EndScreenPerception].screenshot_file_info.get_screenshot_Image_file())
            # 如果不是standalone_reflector_mode，还需要读取前一张图片
            if not self.standalone_reflector_mode:
                images.append(current_action_memory[ActionMemoryType.StartScreenPerception].screenshot_file_info.get_screenshot_Image_file())

        plan_event_content, reflection_event_content = await self.request_llm(
            self.build_prompt(
                instruction_memory.get_instruction(),
                current_action_memory[ActionMemoryType.Plan],
                current_action_memory[ActionMemoryType.Action],
                current_action_memory[ActionMemoryType.ActionResult] if self.standalone_reflector_mode else None,
                current_action_memory[ActionMemoryType.StartScreenPerception] if not self.standalone_reflector_mode else None,
                current_action_memory[ActionMemoryType.EndScreenPerception],
                key_info_memory,
                plan_tips
            ),
            images=images
        )
        # 如果不是standalone_reflector_mode，还需要发布Reflection事件
        if not self.standalone_reflector_mode:
            await self.publish("app_channel", EventMessage(EventType.Reflection_DONE, reflection_event_content))

        # 发布Plan事件，如果不是standalone_reflector_mode且is_finished_action表明行动已经完成执行，则任务结束
        if self.standalone_reflector_mode or not is_finished_action(reflection_event_content, current_action_memory[ActionMemoryType.Action]):
            await asyncio.sleep(5)
            await self.publish("app_channel", EventMessage(EventType.Plan_DONE, plan_event_content))
        else:
            await self.publish("app_channel", EventMessage(EventType.Task_DONE))

        logger.bind(log_tag="fairy_sys").info(f"{self.tag} TASK completed.")

    def build_prompt(self,
                     instruction,
                     plan_info: PlanInfo,
                     action_info: ActionInfo,
                     progress_info: ProgressInfo,
                     previous_screen_perception_info: ScreenInfo,
                     current_screen_perception_info: ScreenInfo,
                     key_infos: list,
                     tips) -> str:
        prompt = f"---\n"\
                 f"The Executor Agent has just finished executing according to your previous plan, which is the sub-goal, action, and expected results of this execution:\n"\
                 f"- Sub-goal: {plan_info.current_sub_goal}\n"\
                 f"- Action(s): {action_info.actions}\n"\
                 f"- Action Expectation: {action_info.action_expectation}\n"\
                 f"\n"

        if self.standalone_reflector_mode:
            # 只有独立反思时才需要提供反思器结果，混合模式下无需提供
            prompt += f"---\n" \
                      f"The reflective agent has just examined the results of the executing agent's execution, which are action results, error potential causes, and progress status.\n"\
                      f"- Action Result: {progress_info.action_result} (A: Successful; B: Partial Successful; C: Failure, incorrect page; D: Failure, page without any change)\n"\
                      f"- Error Potential Causes: {progress_info.error_potential_causes} \n"\
                      f"- Progress Status: {progress_info.progress_status} \n"\
                      f"\n"

        if not self.standalone_reflector_mode:
            prompt += old_and_new_screen_comparison(previous_screen_perception_info, current_screen_perception_info, self.non_visual_mode)
        else:
            prompt += screen(current_screen_perception_info, self.non_visual_mode)

        prompt += f"---\n"\
                  f"- Instruction: {instruction}\n"\
                  f"- Overall Plan: {plan_info.overall_plan}\n"\
                  f"- Key Information Record (Excluding Current Screen): {key_infos}\n" \
                  f"\n"

        prompt += f"---\n"\
                  f"Please follow the steps below to {'' if not self.standalone_reflector_mode else 'check the progress of sub-goal completion and'} consider the need to revise the plan:\n"
        prompt += ordered_list((reflection_steps + replan_steps) if not self.standalone_reflector_mode else replan_steps)
        prompt += "\n"

        prompt += f"---\n"\
                  f"Please follow the steps below to revise the plan if you need:\n"
        prompt += ordered_list(plan_steps)
        prompt += "IMPORTANT: If you are attempting to change a plan, make sure the completed plan (prior to the current_sub_goal) is retained. You can only change plans that have not yet been completed.\n"
        prompt += "\n"

        prompt += "Here's some REQUIREMENTS for developing the plan. These REQUIREMENTS are VERY IMPORTANT, so MAKE SURE you follow them to the letter:\n"
        prompt += unordered_list(plan_requirements)

        prompt += plan_tips(tips)

        prompt += output_json_object((reflection_output + replan_output) if not self.standalone_reflector_mode else replan_output)
        return prompt

    def parse_response(self, response: str) -> (PlanInfo, ProgressInfo):
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        response_jsonobject = json.loads(response)

        plan_info = PlanInfo(response_jsonobject['plan_thought'], response_jsonobject['overall_plan'], response_jsonobject['current_sub_goal'], response_jsonobject['user_interaction_type'], response_jsonobject['user_interaction_thought'])

        if not self.standalone_reflector_mode:
            progress_info = ProgressInfo(response_jsonobject['action_result'], response_jsonobject['error_potential_causes'],
                     response_jsonobject['progress_status'])
        else:
            progress_info = None

        return plan_info, progress_info
