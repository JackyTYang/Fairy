
import json
import re
from typing import List

from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.agents.global_planner_agents.global_planner_common import plan_steps, plan_output
from Fairy.agents.prompt_common import ordered_list, output_json_object
from Fairy.config.fairy_config import FairyConfig
from Fairy.info_entity import GlobalPlanInfo, ActionInfo, ProgressInfo, PlanInfo, InstructionInfo
from Fairy.memory.short_time_memory_manager import ShortMemoryCallType, ActionMemoryType
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventType, CallType


class GlobalRePlannerAgent(Agent):
    def __init__(self, runtime, config: FairyConfig) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to take notes of important content relevant to the user's request.",
            type="SystemMessage")]
        super().__init__(runtime, "GlobalRePlannerAgent", config.model_client, system_messages)


    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.Task_DONE)
    async def on_global_plan(self, message:EventMessage , message_context):
        logger.bind(log_tag="fairy_sys").debug("[Global RePlan] TASK in progress...")
        app_info_list = await (await self.call(
            "AppInfoManager",
            CallMessage(CallType.App_Info_GET,{})
        ))

        short_memory = await (await self.call(
            "ShortTimeMemoryManager",
            CallMessage(CallType.Memory_GET,{
                ShortMemoryCallType.GET_Global_Instruction: None,
                ShortMemoryCallType.GET_Global_Plan_Info:None,
                ShortMemoryCallType.GET_Instruction:None,
                ShortMemoryCallType.GET_Historical_Action_Memory:{ActionMemoryType.Plan: 1, ActionMemoryType.Action:float("INF"), ActionMemoryType.ActionResult:float("INF")},
                ShortMemoryCallType.GET_Key_Info:None
            })
        ))
        user_instruction = short_memory[ShortMemoryCallType.GET_Global_Instruction]
        global_plan_info = short_memory[ShortMemoryCallType.GET_Global_Plan_Info]

        app_instruction_memory = short_memory[ShortMemoryCallType.GET_Instruction]
        app_historical_action_memory = short_memory[ShortMemoryCallType.GET_Historical_Action_Memory]
        app_key_info_memory = short_memory[ShortMemoryCallType.GET_Key_Info]

        global_plan = await self.request_llm(
            self.build_prompt(
                user_instruction,
                app_info_list,
                global_plan_info,
                app_instruction_memory,
                app_historical_action_memory[ActionMemoryType.Plan][0],
                app_historical_action_memory[ActionMemoryType.Action],
                app_historical_action_memory[ActionMemoryType.ActionResult],
                app_key_info_memory
            )
        )

        await self.publish("app_channel", EventMessage(EventType.GlobalPlan_DONE, global_plan))
        logger.bind(log_tag="fairy_sys").info("[Global RePlan] TASK completed.")

    @staticmethod
    def build_prompt(user_instruction:str,
                     app_info_list: dict,
                     global_plan_info: GlobalPlanInfo,
                     app_instruction: InstructionInfo,
                     app_plan_info: PlanInfo,
                     app_action_info_list: List[ActionInfo],
                     app_progress_info_list: List[ProgressInfo],
                     app_key_infos: list) -> str:
        prompt = f"---\n"\
                 f"- User Overall Instruction: {user_instruction}\n"\
                 f"\n"

        prompt += f"- A List of Apps that already exist on the user's device:\n"
        for app_package_name in app_info_list.keys():
            prompt += f"Package: {app_package_name} | Name: {app_info_list[app_package_name]['app_name']} | Desc: {app_info_list[app_package_name]['app_desc']} \n"
        prompt += f"\n"

        prompt += f"---\n"\
                  f"The App-Level Executor has just finished executing according to your previous plan, here is the briefing:\n" \
                  f"- Original Instruction: {app_instruction.ori}\n" \
                  f"- Instructions added by user through interaction: {app_instruction.updated}\n" \
                  f"- App-Level Overall Plan: {app_plan_info.overall_plan}\n" \
                  f"- App-Level Executed Action History:\n"
        for app_progress_info, app_action_info in zip(app_progress_info_list, app_action_info_list):
            action_log_str = f"Action(s): {app_action_info.actions} | " \
                             f"Action Description: {app_action_info.action_expectation} | " \
                             f"Action Result: {'Successful' if app_progress_info.action_result == 'A' else 'Partial Successful' if app_progress_info.action_result == 'B' else 'Failure'} | "
            if app_progress_info.action_result == "C" or app_progress_info.action_result == "D":
                action_log_str += f"Error Potential Causes: {app_progress_info.error_potential_causes} | "
            prompt += f"{action_log_str}\n"
        prompt += f"- App-Level Key Information Collection Request: {app_instruction.key_info_request}\n" \
                  f"- App-Level Collected Key Information : {app_key_infos}\n" \
                  f"\n"

        prompt += f"---\n" \
                  f"- Current Global Plan: {global_plan_info.global_plan}\n"

        prompt += f"---\n"\
                  f"Please follow the steps below to check the progress of sub-task completion and consider the need to revise the global plan:\n"\
                  f"1. Consider whether the application's plan and execution results have met your expectations.\n"\
                  f"2. If the expectations are not met, revise your previous global plan and update the sub-tasks to require the application to continue execution.\n"\
                  f"3. If expectations are met, consider the sub-tasks that need to be completed next and the key information that needs to be delivered to the sub-tasks, which should be collated from the key information gathered for the previous task, taking into account the subtasks to be executed next.\n" \

        prompt += f"---\n"\
                  f"Please follow the steps below to revise the global plan if you need:\n"
        prompt += ordered_list(plan_steps)
        prompt += "\n"

        prompt += f"---\n"\
                  f"NOTE: If there are proprietary applications, do not consider generic applications. For example, if a user wishes to order a Starbucks, a takeaway app should not be considered if a Starbucks app exists. Make sure you consider a mini-program ONLY when there is no other way.\n" \
                  f"\n"

        prompt += output_json_object(
            [
                "- execution_result: The result of the execution of the previous subtask. Please indicate whether the expectations have been met.",
                "- delivered_key_info: The key information that needs to be delivered to the next sub-tasks."
            ] + plan_output)

        return prompt

    def parse_response(self, response: str) -> GlobalPlanInfo:
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        response_jsonobject = json.loads(response)
        action_info = GlobalPlanInfo(
            response_jsonobject['global_plan_thought'],
            response_jsonobject['global_plan'],
            response_jsonobject['current_sub_task'],
            response_jsonobject['ins_language'],
            response_jsonobject['delivered_key_info'],
            response_jsonobject['execution_result']
        )
        return action_info