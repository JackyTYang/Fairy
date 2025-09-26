import json
import re

from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.agents.global_planner_agents.global_planner_common import plan_steps, plan_output
from Fairy.agents.prompt_common import ordered_list, output_json_object
from Fairy.config.fairy_config import FairyConfig
from Fairy.entity.info_entity import GlobalPlanInfo
from Fairy.entity.log_template import LogTemplate, LogEventType
from Fairy.entity.message_entity import EventMessage, CallMessage
from Fairy.entity.type import EventType, CallType, EventChannel, EventStatus


class GlobalPlannerAgent(Agent):
    def __init__(self, runtime, config: FairyConfig) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to take notes of important content relevant to the user's request.",
            type="SystemMessage")]
        super().__init__(runtime, "GlobalPlannerAgent", config.model_client, system_messages)
        self.log_t = LogTemplate(self)  # 日志模板

    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.GLOBAL_CHANNEL,
              listen_filter=lambda msg: msg.match(EventType.INIT, EventStatus.CREATED))
    async def on_global_plan(self, message:EventMessage , message_context):
        # 发布Plan CREATED事件 & 记录日志
        await self.publish(EventChannel.GLOBAL_CHANNEL, EventMessage(EventType.Plan, EventStatus.CREATED))
        logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerStart)("Init Global Plan"))

        app_info_list = await (await self.call(
            "AppInfoManager",
            CallMessage(CallType.App_Info_GET,{})
        ))
        user_instruction = message.event_content["user_instruction"]
        global_plan = await self.request_llm(
            self.build_prompt(
                user_instruction,
                app_info_list
            )
        )

        logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.IntermediateResult)("Init global plan result", global_plan))

        # 发布Plan Done事件 & 记录日志
        await self.publish(EventChannel.GLOBAL_CHANNEL, EventMessage(EventType.Plan, EventStatus.DONE, global_plan))
        logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerCompleted)("Init Global Plan"))

    @staticmethod
    def build_prompt(user_instruction, app_info_list) -> str:
        prompt = f"---\n"\
                 f"- User Overall Instruction: {user_instruction}\n"\
                 f"\n"

        prompt += f"- A List of Apps that already exist on the user's device:\n"
        for app_package_name in app_info_list.keys():
            prompt += f"Package: {app_package_name} | Name: {app_info_list[app_package_name]['app_name']} | Desc: {app_info_list[app_package_name]['app_desc']} \n"
        prompt += f"\n"

        prompt += f"---\n"\
                  f"Please follow these steps to develop a plan:\n"
        prompt += ordered_list(plan_steps)
        prompt += "\n"

        prompt += f"---\n"\
                  f"NOTE: If there are proprietary applications, do not consider generic applications. For example, if a user wishes to order a Starbucks, a takeaway app should not be considered if a Starbucks app exists. Make sure you consider a mini-program ONLY when there is no other way.\n" \
                  f"\n"

        prompt += output_json_object(plan_output + [
                    "current_sub_task: The sub-task you should work on, selected from the 'global_plan'."
            ])

        return prompt

    def parse_response(self, response: str) -> GlobalPlanInfo:
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        response_jsonobject = json.loads(response)
        global_plan_info = GlobalPlanInfo(response_jsonobject['global_plan_thought'], response_jsonobject['global_plan'], response_jsonobject['current_sub_task'], response_jsonobject['ins_language'])
        return global_plan_info