import asyncio
import subprocess
from re import escape
from typing import List, Dict

from loguru import logger

from Fairy.tools.mobile_controller.action_type import AtomicActionType
from Fairy.utils.task_executor import TaskExecutor

ATOMIC_ACTION_COMMAND = {
    AtomicActionType.Tap: lambda args: f"shell input tap {args['x']} {args['y']}",
    AtomicActionType.Swipe: lambda args: f"shell input swipe {args['x1']} {args['y1']} {args['x2']} {args['y2']} {args['duration']}",
    AtomicActionType.LongPress: lambda args: f"shell input swipe {args['x']} {args['y']} {args['x']} {args['y']} {args['duration']}",
    AtomicActionType.Input: lambda args: " shell am broadcast -a ADB_INPUT_TEXT --es msg " + str(escape(args['text']).replace("\'","\\'")),
    AtomicActionType.ClearInput: lambda args: f" shell am broadcast -a ADB_CLEAR_TEXT",
    AtomicActionType.KeyEvent: lambda args: f"shell input keyevent {args['type']}",
}

class AdbMobileController():
    def __init__(self, config):
        self.adb_path = config.get_adb_path()

    async def execute_action(self, actions: List[Dict[str, AtomicActionType | dict]]) -> None:
        for action in actions:
            atomic_action, args = AtomicActionType(action["name"]), action["arguments"]
            match atomic_action:
                case AtomicActionType.Wait:
                    await asyncio.sleep(args["wait_time"])
                case AtomicActionType.Finish:
                    logger.bind(log_tag="fairy_sys").info("All requirements in the user's Instruction have been completed.")
                case AtomicActionType.NeedInteraction:
                    await asyncio.sleep(1)
                    logger.bind(log_tag="fairy_sys").warning("Executor discovery requires user interaction.")
                case _:
                    await self._run_command(atomic_action, ATOMIC_ACTION_COMMAND[atomic_action], args)
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
            logger.bind(log_tag="fairy_sys").debug(f"Executing ADB command {action} : {command}")
            result = subprocess.run(f"{self.adb_path} {command}", capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                raise RuntimeError(f"Error while executing ADB command: {result.stderr}")
            await asyncio.sleep(1)

        await TaskExecutor(f"ADB_Command_{action}_Execute", None).run(_command)
