from enum import Enum
from pathlib import Path

from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter, FilterCondition
from loguru import logger

from Citlali.core.type import ListenerType
from Citlali.core.worker import Worker, listener
from Fairy.config.fairy_config import FairyConfig
from Fairy.entity.log_template import LogEventType, LogTemplate
from Fairy.entity.message_entity import CallMessage
from Fairy.entity.type import CallType

class LongMemoryCallType(Enum):
    GET_Tips = 1

class LongMemoryType(Enum):
    Execution_Tips = "Execution_Tips",
    Execution_ERROR_Tips = "Execution_ERROR_Tips",
    Plan_Tips = "Plan_Tips"

class LongTimeMemoryManager(Worker):
    def __init__(self, runtime, config:FairyConfig):
        super().__init__(runtime, "LongTimeMemoryManager", "LongTimeMemoryManager")
        self.log_t = LogTemplate(self)  # 日志模板

        self.llm = config.rag_model_client

        data_path = Path(__file__).resolve().parent.parent / "data"
        self.index = {
            LongMemoryType.Execution_Tips: VectorStoreIndex.from_documents(SimpleDirectoryReader(data_path / "execution_tips").load_data(),
                                                                           embed_model=config.rag_embed_model_client,
                                                                           show_progress=True),
            LongMemoryType.Execution_ERROR_Tips: VectorStoreIndex.from_documents(SimpleDirectoryReader(data_path / "execution_error_tips").load_data(),
                                                                           embed_model=config.rag_embed_model_client,
                                                                           show_progress=True),
            LongMemoryType.Plan_Tips: VectorStoreIndex.from_documents(SimpleDirectoryReader(data_path / "plan_tips").load_data(),
                                                                           embed_model=config.rag_embed_model_client,
                                                                           show_progress=True),
        }

        self.memory_cache = {
            LongMemoryType.Execution_Tips: {},
            LongMemoryType.Execution_ERROR_Tips: {},
            LongMemoryType.Plan_Tips: {},
        }

    @listener(ListenerType.ON_CALLED, listen_filter=lambda message: message.call_type == CallType.Memory_GET)
    async def get_memory(self, message: CallMessage, message_context):
        memory_list = {}
        for memory_call_type in message.call_content:
            match memory_call_type:
                case LongMemoryCallType.GET_Tips:
                    memory_list[memory_call_type] = self.query_tips(message.call_content[memory_call_type])
                case _:
                    raise ValueError(f"Unsupported memory call type: {memory_call_type}")
        return memory_list

    def query_memory_cache(self, memory_call_type, query_text):
        need_to_move = []
        for key, value in self.memory_cache[memory_call_type].items():
            if key == query_text:
                self.memory_cache[memory_call_type][key]["expires"] = 5
                return value["response"]
            elif value["expires"] > 0:
                self.memory_cache[memory_call_type][key]["expires"] -= 1
            else:
                need_to_move.append(key)
        for key in need_to_move:
            del self.memory_cache[memory_call_type][key]
        return None

    def add_memory_cache(self, memory_call_type, query_text, response):
        self.memory_cache[memory_call_type][query_text] = {
            "response": response,
            "expires": 5
        }

    def query_tips(self, memory_request):
        map = {
            LongMemoryType.Plan_Tips: lambda text: f"The user instruction is '{text}', please find all relevant tips (Including related tasks), then output a numbered list.",
            LongMemoryType.Execution_Tips: lambda text: f"The current sub-goal is '{text}', please find all relevant tips, then output a numbered list.",
            LongMemoryType.Execution_ERROR_Tips:lambda text: f"Just encountered an error, the error message is '{text}', please all the relevant tips, then output line by line."
        }
        memory = {}
        for memory_type in memory_request:
            query_text = memory_request[memory_type]["query"]
            # 查询缓存
            response = self.query_memory_cache(memory_type, query_text)
            if response is not None:
                logger.bind(log_tag="fairy_sys").info(f"Long Memory Cache {query_text} has been hit.")
                memory[memory_type] = response
                continue

            # 缓存未命中
            filters = MetadataFilters(
                filters=[ExactMatchFilter(key="file_name", value="common.txt"),
                         ExactMatchFilter(key="file_name", value=memory_request[memory_type]["app_package_name"] + ".txt")],
                condition=FilterCondition.OR
            )
            query_engine = self.index[memory_type].as_query_engine(llm=self.llm, filters=filters)
            response = query_engine.query(map[memory_type](query_text))

            logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.Notice)(f"RAG Query:{query_text}"))
            logger.bind(log_tag="fairy_sys").debug(self.log_t.log(LogEventType.Notice)(f"RAG Query Response:{response}"))

            # 添加缓存
            self.add_memory_cache(memory_type, query_text, response)
            memory[memory_type] = response
        return memory