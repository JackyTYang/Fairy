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

    async def custom_execute_action(self, atomic_action: AtomicActionType, args) -> str | None | list[str]:
        logger.bind(log_tag="fairy_sys").debug(f"Executing UI Automator Control Command {atomic_action} (args: {args})")
        match atomic_action:
            case AtomicActionType.Swipe:
                result = self.dev.swipe(args['x1'],args['y1'],args['x2'],args['y2'], args['duration']/1000) # 单位是s而不是ms
            case AtomicActionType.Tap:
                result = self.dev.click(args['x'],args['y'])
            case AtomicActionType.LongPress:
                result = self.dev.long_click(args['x'],args['y'],args['duration'])
            case AtomicActionType.Input:
                result = self.dev.send_keys(args['text']) # input from pasteboard
            case AtomicActionType.ClearInput:
                result = self.dev.clear_text()
            case AtomicActionType.KeyEvent:
                result = self.dev.press(keycode_list[args['type']])
            case AtomicActionType.ListApps:
                result = self.dev.app_list(filter="-3")
            case AtomicActionType.StartApp:
                result = self.dev.app_start(args['app_package_name'], wait=True)
            case _:
                raise RuntimeError(f"Unknown atomic action: {atomic_action}")
        await asyncio.sleep(2)
        return result
