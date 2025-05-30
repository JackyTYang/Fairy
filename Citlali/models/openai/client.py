import asyncio
import inspect
import os
from typing import List, Sequence, Mapping, Any, cast, AsyncGenerator

from loguru import logger
from openai import AsyncOpenAI
from openai.resources.chat import AsyncCompletions
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam, \
    ChatCompletionContentPartImageParam, ChatCompletionContentPartTextParam, ChatCompletionChunk
from openai.types.chat.chat_completion_content_part_image_param import ImageURL

from ..entity import ChatMessage, ModelUsage, ResultMessage
from ..model_client import ChatClient
from ...utils.image import Image


class OpenAIChatMessage(ChatMessage):
    def convert(self):
        match self.type:
            case "SystemMessage":
                return ChatCompletionSystemMessageParam(
                    content=self.content,
                    role="system",
                )
            case "UserMessage":
                if isinstance(self.content, str):
                    content = f"{self.source} said:\n" + self.content
                elif isinstance(self.content, List):
                    content = []
                    for content_item in self.content:
                        if isinstance(content_item, str):
                            content.append(
                                ChatCompletionContentPartTextParam(
                                    text=content_item,
                                    type="text",
                                )
                            )
                        elif isinstance(content_item, Image):
                            content.append(
                                ChatCompletionContentPartImageParam(
                                    image_url=ImageURL(
                                        url=content_item.to_data_uri(),
                                        detail="auto"
                                    ),
                                    type="image_url"
                                )
                            )
                else:
                    raise ValueError("Unsupported content type")
                return ChatCompletionUserMessageParam(
                    content=content,
                    role="user",
                    name=self.source,
                )


class OpenAIChatClient(ChatClient):

    def __init__(self, create_args):
        super().__init__(os.path.dirname(__file__)+"/model_info.json", **create_args)
        self._client = self._init_client(create_args)
        self._create_args = create_args

    @staticmethod
    def _init_client(create_args):
        openai_init_kwargs = set(inspect.getfullargspec(AsyncOpenAI.__init__).kwonlyargs)
        openai_config = {k: v for k, v in create_args.items() if k in openai_init_kwargs}
        return AsyncOpenAI(**openai_config)

    async def create(
            self,
            messages: Sequence[ChatMessage],
            json_output: bool = False,
            extra_create_args: Mapping[str, Any] = {},
    ):
        create_args = self._create_args.copy()
        create_args.update(extra_create_args)


        # 检查图像支持
        if self.model_info["vision"] is False:
            for message in messages:
                if isinstance(message.content, list) and any(isinstance(x, Image) for x in message.content):
                    raise ValueError("Model does not support vision but image was provided")

        # 检查JSON输出支持，并设置response_format
        if json_output and self.model_info["json_output"] is False:
                raise ValueError("Model does not support JSON output.")
        else:
            create_args["response_format"] = {"type": "json_object"} if json_output else {"type": "text"}

        # 转换消息
        messages = [OpenAIChatMessage.convert(message) for message in messages]

        openai_create_kwargs = set(inspect.signature(AsyncCompletions.create).parameters)
        create_args = {k: v for k, v in create_args.items() if k in openai_create_kwargs}

        # 创建对话
        future = asyncio.ensure_future(
            self._client.chat.completions.create(
                messages=messages,
                **create_args,
            )
        )
        # 检查是否需要使用stream
        if create_args.get("stream", False):
            # 如果是stream
            async def _create_stream_chunks() -> AsyncGenerator[ChatCompletionChunk, None]:
                stream = await future
                while True:
                    try:
                        chunk_future = asyncio.ensure_future(anext(stream))
                        chunk = await chunk_future
                        yield chunk
                    except StopAsyncIteration:
                        break

            chunks = _create_stream_chunks()
            chunk= None
            finish_reason = None
            thought_deltas = []
            content_deltas = []
            async for chunk in chunks:
                if len(chunk.choices) == 0:
                    logger.bind(log_tag="citlali_sys").warning(f"Received empty chunk and it is being ignored.")
                    continue
                elif len(chunk.choices) > 1:
                    logger.bind(log_tag="citlali_sys").warning(f"Received a result with {len(chunk.choices)} choices. Only the first choice will be used.")
                choice = chunk.choices[0]

                finish_reason = choice.finish_reason if chunk.usage is None and finish_reason is None else finish_reason

                if choice.delta.model_extra is not None and "reasoning_content" in choice.delta.model_extra:
                    reasoning_content = choice.delta.model_extra.get("reasoning_content")
                    thought_deltas.append(reasoning_content)

                if choice.delta.content:
                    content_deltas.append(choice.delta.content)

            content = "".join(content_deltas).lstrip().rstrip()
            if thought_deltas:
                thought = "".join(thought_deltas).lstrip().rstrip()
            else:
                thought = None

            usage = ModelUsage(
                prompt_tokens = chunk.usage.prompt_tokens if chunk and chunk.usage else 0,
                completion_tokens = chunk.usage.completion_tokens if chunk and chunk.usage else 0)
        else:
            # 如果不是stream
            result = await future

            # 构建ResultMessage响应, 只保留第一个Choice
            if len(result.choices) > 1:
                logger.bind(log_tag="citlali_sys").warning(f"Received a result with {len(result.choices)} choices. Only the first choice will be used.")
            choice = result.choices[0]

            finish_reason = choice.finish_reason

            # 获取Token用量信息
            usage = ModelUsage(
                prompt_tokens=result.usage.prompt_tokens if result.usage is not None else 0,
                completion_tokens=(result.usage.completion_tokens if result.usage is not None else 0),
            )
            content = choice.message.content or ""
            thought = None

        response = ResultMessage(
            finish_reason = finish_reason,
            content = content,
            thought = thought,
            usage=usage,
        )

        logger.bind(log_tag="citlali_sys").debug(f"Token consumption for this request: {usage}")
        return response


