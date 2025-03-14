import asyncio
import subprocess

from loguru import logger

from Citlali.core.agent import Worker
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Fairy.message_entity import EventMessage
from Fairy.type import EventType, EventStatus
from ..tools.action_type import AtomicActionType
from ..utils.task_executor import TaskExecutor


class OperationExecution(Worker):
    def __init__(self, runtime, config):
        super().__init__(runtime, "OperationExecution", "OperationExecution")
        self.adb_path = config.adb_path

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.ActionExecution and message.status == EventStatus.CREATED)
    async def on_action_create(self, message: EventMessage, message_context):
        logger.debug("Get action execute task in progress...")
        await self.execute_action(message.event_content.action, message.event_content.args)
        logger.debug("Get action execute task completed.")
        await self.publish("app_channel", EventMessage(EventType.ActionExecution, EventStatus.DONE, message.event_content))

    async def execute_action(self, action: AtomicActionType, args: dict, **kwargs) -> None:
        match action:
            # case AtomicActionType.Open_App:
            #     await self._start_app(args["app_name"])
            #     await asyncio.sleep(2)
            case AtomicActionType.Tap:
                await self._tap(args["x"], args["y"])
                await asyncio.sleep(2)
            case AtomicActionType.Swipe:
                await self._swipe(args["x1"], args["y1"], args["x2"], args["y2"])
                await asyncio.sleep(2)
            case AtomicActionType.Type:
                await self._type(args["text"])
                await asyncio.sleep(2)
            case AtomicActionType.Switch_App:
                await self._input_key("KEYCODE_APP_SWITCH")
                await asyncio.sleep(2)
            case AtomicActionType.Back:
                await self._input_key("KEYCODE_BACK")
                await asyncio.sleep(2)
            case AtomicActionType.Home:
                await self._input_key("KEYCODE_HOME")
                await asyncio.sleep(2)
            case AtomicActionType.Wait:
                await asyncio.sleep(args["wait_time"])

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

    async def _type(self, text):
        async def _type():
            result = subprocess.run(self.adb_path + f" shell am broadcast -a ADB_INPUT_TEXT --es msg \"{text}\"", capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                raise RuntimeError(f"Error occurred while typing text: {result.stderr}")
            await asyncio.sleep(1)

        await TaskExecutor("[ATOM OP] Type_Text", None).run(_type)

    async def _tap(self, x, y):
        async def _tap():
            result = subprocess.run(f"{self.adb_path} shell input tap {x} {y}", capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                raise RuntimeError(f"Error occurred while tapping: {result.stderr}")
            await asyncio.sleep(1)
        await TaskExecutor("[ATOM OP] Tap", None).run(_tap)

    async def _swipe(self, x1, y1, x2, y2, duration=500):
        async def _swipe():
            result = subprocess.run(f"{self.adb_path} shell input swipe {x1} {y1} {x2} {y2} {duration}", capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                raise RuntimeError(f"Error occurred while swiping: {result.stderr}")
            await asyncio.sleep(1)
        await TaskExecutor("[ATOM OP] Swipe", None).run(_swipe)

    async def _input_key(self, key_code: str):
        async def _input_key():
            result = subprocess.run(f"{self.adb_path} shell input keyevent {key_code}", capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                raise RuntimeError(f"Error occurred while input key {key_code}: {result.stderr}")
            await asyncio.sleep(1)
        await TaskExecutor("[ATOM OP] Input_Key", None).run(_input_key)
