import asyncio
from typing import List, Dict

from loguru import logger

from Fairy.tools.mobile_controller.action_type import AtomicActionType
import uiautomator2 as u2

from Fairy.tools.mobile_controller.entity import MobileController

keycode_list = {
    "KEYCODE_BACK": "back",
    "KEYCODE_HOME": "home",
    "KEYCODE_ENTER": "enter",
}

class UiAutomatorMobileController(MobileController):
    def __init__(self, config):
        self.dev = u2.connect(config.device)

    async def execute_actions(self, actions: List[Dict[str, AtomicActionType | dict]]) -> None:
        for action in actions:
            atomic_action, args = AtomicActionType(action["name"]), action["arguments"]
            await self.execute_action(atomic_action, args)

    async def execute_action(self, atomic_action: AtomicActionType, args) -> str  | None | list[str]:
        result = await self._run_command(atomic_action, args)
        await asyncio.sleep(2)
        return result

    async def _run_command(self, action: AtomicActionType, args) -> str | None | list[str]:
        logger.bind(log_tag="fairy_sys").debug(f"Executing UI Automator Control Command {action} (args: {args})")
        match action:
            case AtomicActionType.Swipe:
                return self.dev.swipe(args['x1'],args['y1'],args['x2'],args['y2'],args['duration'])
            case AtomicActionType.Tap:
                return self.dev.click(args['x'],args['y'])
            case AtomicActionType.LongPress:
                return self.dev.long_click(args['x'],args['y'],args['duration'])
            case AtomicActionType.Input:
                return self.dev.send_keys(args['text']) # input from pasteboard
            case AtomicActionType.ClearInput:
                return self.dev.clear_text()
            case AtomicActionType.KeyEvent:
                return self.dev.press(keycode_list[args['type']])
            case AtomicActionType.Finish:
                logger.bind(log_tag="fairy_sys").info("All requirements in the user's Instruction have been completed.")
                return None
            case AtomicActionType.Wait:
                await asyncio.sleep(args["wait_time"])
                return None
            case AtomicActionType.NeedInteraction:
                await asyncio.sleep(1)
                logger.bind(log_tag="fairy_sys").warning("Executor discovery requires user interaction.")
                return None
            case AtomicActionType.ListApps:
                return self.dev.app_list(filter="-3")
            case AtomicActionType.StartApp:
                return self.dev.app_start(args['app_package_name'], wait=True)
