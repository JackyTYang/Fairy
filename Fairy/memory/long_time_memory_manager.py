from enum import Enum
from pathlib import Path

from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
from loguru import logger

from Citlali.core.type import ListenerType
from Citlali.core.worker import Worker, listener
from Fairy.config.fairy_config import FairyConfig
from Fairy.message_entity import CallMessage
from Fairy.type import CallType

class LongMemoryCallType(Enum):
    GET_Execution_Tips = 1
    GET_Execution_ERROR_Tips = 2
    GET_Plan_Tips = 3

class LongTimeMemoryManager(Worker):
    def __init__(self, runtime, config:FairyConfig):
        super().__init__(runtime, "LongTimeMemoryManager", "LongTimeMemoryManager")

        self.llm = config.rag_model_client

        data_path = Path(__file__).resolve().parent.parent / "data"
        self.index = VectorStoreIndex.from_documents(
            SimpleDirectoryReader(data_path).load_data(),
            embed_model=config.rag_embed_model_client,
            show_progress=True
        )

        self.memory_cache = {
            LongMemoryCallType.GET_Execution_Tips: {},
            LongMemoryCallType.GET_Execution_ERROR_Tips: {},
            LongMemoryCallType.GET_Plan_Tips: {},
        }

    @listener(ListenerType.ON_CALLED, listen_filter=lambda message: message.call_type == CallType.Memory_GET)
    async def get_memory(self, message: CallMessage, message_context):
        memory_list = {}
        for memory_call_type in message.call_content:
            memory = None
            match memory_call_type:
                case LongMemoryCallType.GET_Execution_Tips:
                    memory = self.query_tips(memory_call_type, message.call_content[memory_call_type])
                case LongMemoryCallType.GET_Plan_Tips:
                    memory = self.query_tips(memory_call_type, message.call_content[memory_call_type])
                case LongMemoryCallType.GET_Execution_ERROR_Tips:
                    memory = self.query_tips(memory_call_type, message.call_content[memory_call_type])
            memory_list[memory_call_type] = memory
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

    def query_tips(self, memory_call_type, query_text):
        response = self.query_memory_cache(memory_call_type, query_text)
        if response is not None:
            logger.bind(log_tag="fairy_sys").info(f"Long Memory Cache {query_text} has been hit.")
            return response
        map = {
            LongMemoryCallType.GET_Plan_Tips: {
                "file_name": "plan_tips.txt",
                "query": lambda text: f"The user instruction is '{text}', please find all relevant tips (Including related tasks), then output a numbered list."
            },
            LongMemoryCallType.GET_Execution_Tips:{
                "file_name": "execution_tips.txt",
                "query": lambda text: f"The current sub-goal is '{text}', please find all relevant tips, then output a numbered list."
            },
            LongMemoryCallType.GET_Execution_ERROR_Tips: {
                "file_name": "execution_error_tips.txt",
                "query": lambda
                    text: f"Just encountered an error, the error message is '{text}', please all the relevant tips, then output line by line."
            }
        }
        filters = MetadataFilters(
            filters=[ExactMatchFilter(key="file_name", value=map[memory_call_type]["file_name"])]
        )
        query_engine = self.index.as_query_engine(llm=self.llm, filters=filters)
        response = query_engine.query(map[memory_call_type]["query"](query_text))
        self.add_memory_cache(memory_call_type, query_text, response)
        return response