import functools
from typing import List

from loguru import logger

from .worker import Worker
from ..models.entity import ChatMessage
from ..utils.image import Image


class Agent(Worker):
    def __init__(self, runtime, name, model_client, system_messages, desc=None):
        super().__init__(runtime, name ,desc)
        self._model_client = model_client
        self._system_messages = system_messages

    async def request_llm(self, content: str, images: List[Image] = []):
        user_message = ChatMessage(content=[content]+images, type="UserMessage", source="user")
        response = await self._model_client.create(
            self._system_messages + [user_message]
        )
        response = self.parse_response(response.content)
        logger.debug("LLM Response: " + str(response))
        return response

    def parse_response(self, content: str):
        ...