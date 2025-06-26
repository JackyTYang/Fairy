import asyncio
import subprocess
from re import escape
from typing import List, Dict

from loguru import logger

from Fairy.entity.log_template import LogEventType, LogTemplate
from Fairy.tools.mobile_controller.action_type import AtomicActionType
from Fairy.tools.mobile_controller.entity import MobileController
from Fairy.utils.task_executor import TaskExecutor

ATOMIC_ACTION_COMMAND = {
    AtomicActionType.Tap: lambda args: f"shell input tap {args['x']} {args['y']}",
    AtomicActionType.Swipe: lambda args: f"shell input swipe {args['x1']} {args['y1']} {args['x2']} {args['y2']} {args['duration']}",
    AtomicActionType.LongPress: lambda args: f"shell input swipe {args['x']} {args['y']} {args['x']} {args['y']} {args['duration']}",
    AtomicActionType.Input: lambda args: " shell am broadcast -a ADB_INPUT_TEXT --es msg " + str(escape(args['text']).replace("\'","\\'")),
    AtomicActionType.ClearInput: lambda args: f" shell am broadcast -a ADB_CLEAR_TEXT",
    AtomicActionType.KeyEvent: lambda args: f"shell input keyevent {args['type']}",
    AtomicActionType.ListApps: lambda args: f"shell pm list packages -3",
    AtomicActionType.StartApp: lambda args: f"shell monkey -p {args['app_package_name']} -c android.intent.category.LAUNCHER 1",
}

class AdbMobileController(MobileController):
    def __init__(self, config):
        self.adb_path = config.get_adb_path()

        self.log_t = LogTemplate(self, "AdbMobileController")  # 日志模板

    async def custom_execute_action(self, atomic_action: AtomicActionType, args) -> str | None | list[str]:
        match atomic_action:
            case AtomicActionType.ListApps:
                result = await self._run_command(AtomicActionType.ListApps, ATOMIC_ACTION_COMMAND[AtomicActionType.ListApps], args)
                result = result.replace("package:","").splitlines()
                return result
            case _:
                result = await self._run_command(atomic_action, ATOMIC_ACTION_COMMAND[atomic_action], args)
                await asyncio.sleep(2) # Avoid screen not updating due to phone lag
                return result

    async def _run_command(self, action: AtomicActionType, command_builder, args):
        async def _command():
            command = command_builder(args)
            logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.Notice)(f"Executing Action: {action} (args: {args})"))
            logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.Notice)(f"Executing ADB Command: {command}"))

            result = subprocess.run(f"{self.adb_path} {command}", capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                raise RuntimeError(f"Error while executing ADB command: {result.stderr}")
            await asyncio.sleep(1)
            return result.stdout

        return await TaskExecutor(f"ADB_Command_{action}_Execute", None).run(_command)
