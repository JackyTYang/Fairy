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
        logger.bind(log_tag="agent_req&res").info(f"[Request]\n{content}")
        user_message = ChatMessage(content=[content]+images, type="UserMessage", source="user")
        logger.bind(log_tag="citlali_sys").debug(f"Requesting LLM...")
        response = await self._model_client.create(
            self._system_messages + [user_message]
        )
        logger.bind(log_tag="citlali_sys").debug(f"Requesting LLM done.")
        responses = self.parse_response(response.content)
        if isinstance(responses, tuple):
            for r in responses:
                logger.bind(log_tag="agent_req&res").info(f"[Response]\n{str(r)}")
        else:
            logger.bind(log_tag="agent_req&res").info("Response]" + str(responses))
        return responses

    def parse_response(self, content: str):
        ...