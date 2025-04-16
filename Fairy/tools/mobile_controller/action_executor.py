from typing import List, Dict

from loguru import logger

from Citlali.core.agent import Worker
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Fairy.config.fairy_config import MobileControllerType
from Fairy.message_entity import EventMessage
from Fairy.type import EventType, EventStatus
from Fairy.tools.mobile_controller.adb_tools.mobile_control_tool import AdbMobileController
from Fairy.tools.mobile_controller.ui_automator_tools.mobile_control_tool import UiAutomatorMobileController
from Fairy.tools.mobile_controller.action_type import AtomicActionType


class ActionExecutor(Worker):
    def __init__(self, runtime, config):
        super().__init__(runtime, "ActionExecutor", "ActionExecutor")

        self.action_executor_type = config.action_executor_type
        if self.action_executor_type == MobileControllerType.ADB:
            self.control_tool = AdbMobileController(config)
        elif self.action_executor_type == MobileControllerType.UIAutomator:
            self.control_tool = UiAutomatorMobileController(config)

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.ActionExecution and message.status == EventStatus.CREATED)
    async def on_action_create(self, message: EventMessage, message_context):
        logger.bind(log_tag="fairy_sys").debug("[Execute action] TASK in progress...")
        await self.execute_action(message.event_content.actions)
        logger.bind(log_tag="fairy_sys").debug("[Execute action] TASK completed.")
        await self.publish("app_channel", EventMessage(EventType.ActionExecution, EventStatus.DONE, message.event_content))

    async def execute_action(self, actions: List[Dict[str, AtomicActionType | dict]]) -> None:
        await self.control_tool.execute_action(actions)