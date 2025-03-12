from Citlali.core.type import ListenerType
from Citlali.core.worker import Worker, listener
from Fairy.message.action_message import ActionMessage
from Fairy.tools.screen_perception import ScreenPerception


class ScreenManager(Worker):
    def __init__(self, runtime, config):
        super().__init__(runtime, "ScreenManager", "ScreenManager")
        self.screen_perception = ScreenPerception(runtime, config)

        self.screen_descriptions = []
        self.screen_shot = []


    @listener(ListenerType.ON_NOTIFIED, channel="action_channel")
    async def on_action_done(self, message: ActionMessage, message_context):
        await self.screen_perception.get_screen_description()

