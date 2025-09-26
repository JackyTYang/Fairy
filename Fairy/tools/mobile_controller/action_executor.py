from typing import List, Dict

from loguru import logger

from Citlali.core.agent import Worker
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Fairy.config.fairy_config import MobileControllerType
from Fairy.entity.log_template import LogTemplate, LogEventType
from Fairy.entity.message_entity import EventMessage, CallMessage
from Fairy.entity.type import EventType, CallType, EventChannel, EventStatus
from Fairy.tools.mobile_controller.adb_tools.mobile_control_tool import AdbMobileController
from Fairy.tools.mobile_controller.ui_automator_tools.mobile_control_tool import UiAutomatorMobileController
from Fairy.tools.mobile_controller.action_type import AtomicActionType


class ActionExecutor(Worker):
    def __init__(self, runtime, config):
        super().__init__(runtime, "ActionExecutor", "ActionExecutor")
        self.log_t = LogTemplate(self)  # 日志模板

        self.action_executor_type = config.action_executor_type
        if self.action_executor_type == MobileControllerType.ADB:
            self.control_tool = AdbMobileController(config)
        elif self.action_executor_type == MobileControllerType.UIAutomator:
            self.control_tool = UiAutomatorMobileController(config)

    @listener(ListenerType.ON_CALLED, listen_filter=lambda message: message.call_type == CallType.Action_EXECUTE)
    async def do_action(self, message: CallMessage, message_context):
        return await self.execute_action(message.call_content["atomic_action"], message.call_content["args"])

    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.APP_CHANNEL,
              listen_filter=lambda msg: msg.match(EventType.ActionDecision, EventStatus.DONE))
    async def on_action_create(self, message: EventMessage, message_context):
        # 发布ActionExecution CREATED事件 & 记录日志
        await self.publish(EventChannel.APP_CHANNEL, EventMessage(EventType.ActionExecution, EventStatus.CREATED))
        logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerStart)("Action Execution"))

        await self.execute_actions(message.event_content.actions)

        # 发布ActionExecution Done事件 & 记录日志
        await self.publish(EventChannel.APP_CHANNEL, EventMessage(EventType.ActionExecution, EventStatus.DONE, message.event_content))
        logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerCompleted)("Action Execution"))

    async def execute_action(self, atomic_action: AtomicActionType, args) -> str  | None | list[str]:
        result = await self.control_tool.execute_action(atomic_action, args)
        logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.IntermediateResult)("Action execution result", result))
        return result

    async def execute_actions(self, actions: List[Dict[str, AtomicActionType | dict]]) -> None:
        await self.control_tool.execute_actions(actions)