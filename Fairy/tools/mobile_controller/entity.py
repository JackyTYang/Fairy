from typing import List, Dict, Tuple

from Fairy.info_entity import ScreenFileInfo
from Fairy.tools.mobile_controller.action_type import AtomicActionType


class MobileController:

    async def execute_actions(self, actions: List[Dict[str, AtomicActionType | dict]]) -> None:
        ...

    async def execute_action(self, atomic_action: AtomicActionType, args) -> str | None | list[str]:
        ...

class MobileScreenshot:

    async def get_screen(self) -> Tuple[ScreenFileInfo, str | None]:
        ...