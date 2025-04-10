import asyncio
import subprocess
from typing import List, Dict

from loguru import logger

from Citlali.core.agent import Worker
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Fairy.message_entity import EventMessage
from Fairy.type import EventType, EventStatus
from .adb_tools.mobile_control_tool import AdbMobileController
from .ui_automator_tools.mobile_control_tool import UiAutomatorMobileController
from ..tools.action_type import AtomicActionType, ATOMIC_ACTION_SIGNITURES
from ..utils.task_executor import TaskExecutor


class ActionExecutor(Worker):
    def __init__(self, runtime, config):
        super().__init__(runtime, "ActionExecutor", "ActionExecutor")

        self.action_executor_type = config.action_executor_type
        if self.action_executor_type == "adb":
            self.control_tool = AdbMobileController(config)
        elif self.action_executor_type == "uiautomator":
            self.control_tool = UiAutomatorMobileController(config)

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.ActionExecution and message.status == EventStatus.CREATED)
    async def on_action_create(self, message: EventMessage, message_context):
        logger.debug("Get action execute task in progress...")
        await self.execute_action(message.event_content.actions)
        logger.debug("Get action execute task completed.")
        await self.publish("app_channel", EventMessage(EventType.ActionExecution, EventStatus.DONE, message.event_content))

    async def execute_action(self, actions: List[Dict[str, AtomicActionType | dict]]) -> None:
        await self.control_tool.execute_action(actions)