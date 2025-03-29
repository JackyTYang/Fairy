from loguru import logger

from Citlali.core.agent import Worker
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Fairy.message_entity import EventMessage
from Fairy.type import EventType, EventStatus

class UserChat(Worker):
    def __init__(self, runtime):
        super().__init__(runtime, "UserChat", "UserChat")

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.UserChat and message.status == EventStatus.CREATED)
    async def on_action_create(self, message: EventMessage, message_context):
        logger.debug("Interacting with the user for further instruction...")
        user_response = input(message.event_content.action_instruction+"\n")
        logger.debug(f"Further instructions have been obtained. Instruction：{user_response}")

        message.event_content.user_response = user_response
        await self.publish("app_channel", EventMessage(EventType.UserChat, EventStatus.DONE, message.event_content))