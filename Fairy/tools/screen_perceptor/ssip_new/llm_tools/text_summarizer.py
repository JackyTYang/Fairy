import asyncio
import json

from Citlali.models.entity import ChatMessage
from Citlali.models.openai.client import OpenAIChatClient
from Fairy.config.model_config import ModelConfig


class TextSummarizer:
    def __init__(self, text_summarizer_model_config: ModelConfig):
        self._model_client = OpenAIChatClient({
            'model': text_summarizer_model_config.model_name,
            'base_url': text_summarizer_model_config.api_base,
            'api_key': text_summarizer_model_config.api_key,
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
        print(text)
        print(response.content)
        return response.content

    async def summarize_text(self, text_list):
        prompt = 'This is the content of a clickable element on a cell phone, please briefly summarize it in one sentence:'
        tasks = [
            self._request_llm(prompt, text) for text in text_list
        ]
        results = await asyncio.gather(*tasks)
        return {i: result for i, result in enumerate(results)}



async def main():
    ts = TextSummarizer(ModelConfig(
        model_name="qwen",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-d4e50bd7e07747b4827611c28da95c23",
    ))
    print(await ts.summarize_text(["- Img (iv_bg) [The image is a promotional icon for a McDonald\'s \'My Gold Big Mac\' meal, showing a burger, fries, and a drink, with a price reduction from ¥60 to ¥31.]- Img (iv_food) [The image is a promotional graphic for McDonald\'s featuring a large burger, fries, and a soda, with the iconic golden arches logo in the background.]- Img (iv_label) [The image is a red promotional icon with the text '立省 ¥29' indicating a savings of 29 yen.]- LinearLayout- Txt (tv_label_price_prefix) [¥ ]- Txt (tv_label_price) [29 ]- Txt (tv_title) [My Gold Big Mac™ 4pc Combo]- Txt (tv_price) [¥31]- Txt (tv_separate_price) [¥60]"]))

if __name__ == '__main__':
    asyncio.run(main())
