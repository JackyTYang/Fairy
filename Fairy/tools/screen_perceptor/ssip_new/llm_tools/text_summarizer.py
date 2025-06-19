import asyncio
import json

from Citlali.models.entity import ChatMessage
from Citlali.models.openai.client import OpenAIChatClient
from Fairy.config.model_config import ModelConfig


class TextSummarizer:
    def __init__(self, text_summarization_model_config: ModelConfig):
        self._model_client = OpenAIChatClient({
            'model': text_summarization_model_config.model_name,
            'base_url': text_summarization_model_config.api_base,
            'api_key': text_summarization_model_config.api_key,
            'model_info': {"vision": True}
        })

    async def _request_llm(self, prompt, text):
        if len(text) == 0:
            return None
        text = json.dumps(text, ensure_ascii=False)

        user_message = ChatMessage(content=[prompt + text], type="UserMessage", source="user")
        response = await self._model_client.create(
            [user_message]
        )
        return response.content

    async def summarize_text(self, text_list):
        prompt = 'This is the content of a clickable element on a cell phone, please briefly summarize it in one sentence:'
        tasks = [
            self._request_llm(prompt, text) for text in text_list
        ]
        results = await asyncio.gather(*tasks)
        return {i: result for i, result in enumerate(results)}