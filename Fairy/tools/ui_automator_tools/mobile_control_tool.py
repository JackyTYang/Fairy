import asyncio
from re import escape
from typing import List, Dict

from loguru import logger

from Fairy.tools.action_type import AtomicActionType
import uiautomator2 as u2

keycode_list = {
    "KEYCODE_BACK": "back",
    "KEYCODE_HOME": "home",
    "KEYCODE_ENTER": "enter",
}

class UiAutomatorMobileController():
    def __init__(self, device):
        self.dev = u2.connect(device)

    async def execute_action(self, actions: List[Dict[str, AtomicActionType | dict]]) -> None:
        for action in actions:
            atomic_action, args = AtomicActionType(action["name"]), action["arguments"]
            await self._run_command(atomic_action, args)
            await asyncio.sleep(2) # Avoid screen not updating due to phone lag

    async def _run_command(self, action: AtomicActionType, args):
        logger.debug(f"Executing UI Automator Control Command {action} (args: {args})")
        match action:
            case AtomicActionType.Swipe:
                self.dev.swipe(args['x1'],args['y1'],args['x2'],args['y2'],args['duration'])
            case AtomicActionType.Tap:
                self.dev.click(args['x'],args['y'])
            case AtomicActionType.LongPress:
                self.dev.long_click(args['x'],args['y'],args['duration'])
            case AtomicActionType.Input:
                self.dev.send_keys(args['text']) # input from pasteboard
            case AtomicActionType.ClearInput:
                self.dev.clear_text()
            case AtomicActionType.KeyEvent:
                self.dev.press(keycode_list[args['type']])
            case AtomicActionType.Finish:
                logger.info("All requirements in the user's Instruction have been completed.")
            case AtomicActionType.Wait:
                await asyncio.sleep(args["wait_time"])

