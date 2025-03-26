import asyncio
import subprocess
from typing import List, Dict

from loguru import logger

from Citlali.core.agent import Worker
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Fairy.message_entity import EventMessage
from Fairy.type import EventType, EventStatus
from ..tools.action_type import AtomicActionType, ATOMIC_ACTION_SIGNITURES
from ..utils.task_executor import TaskExecutor


class ActionExecutor(Worker):
    def __init__(self, runtime, config):
        super().__init__(runtime, "ActionExecutor", "ActionExecutor")
        self.adb_path = config.get_adb_path()

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.ActionExecution and message.status == EventStatus.CREATED)
    async def on_action_create(self, message: EventMessage, message_context):
        logger.debug("Get action execute task in progress...")
        await self.execute_action(message.event_content.actions)
        logger.debug("Get action execute task completed.")
        await self.publish("app_channel", EventMessage(EventType.ActionExecution, EventStatus.DONE, message.event_content))

    async def execute_action(self, actions: List[Dict[str, AtomicActionType | dict]]) -> None:
        for action in actions:
            atomic_action, args = AtomicActionType(action["name"]), action["arguments"]
            match atomic_action:
                case AtomicActionType.Wait:
                    await asyncio.sleep(args["wait_time"])
                case AtomicActionType.Finish:
                    logger.info("All requirements in the user's Instruction have been completed.")
                case _:
                    await self._run_command(atomic_action, ATOMIC_ACTION_SIGNITURES[atomic_action]['command'], args)
                    await asyncio.sleep(2) # Avoid screen not updating due to phone lag

    async def _get_app_list(self):
        async def _get_app_list():
            result = subprocess.run(f"{self.adb_path} shell pm list packages", capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                raise RuntimeError(f"Error occurred while obtaining app list: {result.stderr}")
            await asyncio.sleep(1)
        await TaskExecutor("Get_App_List", None).run(_get_app_list)

    async def _start_app(self, app_name):
        async def _start_app():
            result = subprocess.run(f"{self.adb_path} shell monkey -p {app_name} -c android.intent.category.LAUNCHER 1", capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                raise RuntimeError(f"Error occurred while starting app: {result.stderr}")


            await asyncio.sleep(1)
        await TaskExecutor("Start_App", None).run(_start_app)

    async def _run_command(self, action: AtomicActionType, command_builder, args):
        async def _command():
            command = command_builder(args)
            logger.debug(f"Executing ADB command {action} : {command}")
            result = subprocess.run(f"{self.adb_path} {command}", capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                raise RuntimeError(f"Error while executing ADB command: {result.stderr}")
            await asyncio.sleep(1)

        await TaskExecutor(f"ADB_Command_{action}_Execute", None).run(_command)
