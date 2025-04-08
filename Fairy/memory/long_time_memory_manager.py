from enum import Enum

from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai_like import OpenAILike

from Citlali.core.type import ListenerType
from Citlali.core.worker import Worker, listener
from Fairy.message_entity import CallMessage
from Fairy.type import CallType

class LongMemoryCallType(Enum):
    GET_Execution_Tips = 1
    GET_Execution_ERROR_Tips = 2
    GET_Plan_Tips = 3

class LongTimeMemoryManager(Worker):
    def __init__(self, runtime):
        super().__init__(runtime, "LongTimeMemoryManager", "LongTimeMemoryManager")

        self.llm = OpenAILike(model="qwen-long", api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
                              api_key="sk-d4e50bd7e07747b4827611c28da95c23", is_chat_model=True, temperature=0)
        
        embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
        self.index = VectorStoreIndex.from_documents(SimpleDirectoryReader("./Fairy/data").load_data(), embed_model=embed_model, show_progress=True)

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

    def query_tips(self, memory_call_type, query_text):
        map = {
            LongMemoryCallType.GET_Plan_Tips: {
                "file_name": "plan_tips.txt",
                "query": lambda text: f"The user instruction is '{text}', please find all relevant tips, then output the results line by line."
            },
            LongMemoryCallType.GET_Execution_Tips:{
                "file_name": "execution_tips.txt",
                "query": lambda text: f"The current subgoal is '{text}', please find all relevant tips, then output the results line by line."
            },
            LongMemoryCallType.GET_Execution_ERROR_Tips: {
                "file_name": "execution_error_tips.txt",
                "query": lambda
                    text: f"Just encountered an error, the error message is '{text}', please all the relevant tips, then output the results line by line."
            }
        }
        filters = MetadataFilters(
            filters=[ExactMatchFilter(key="file_name", value=map[memory_call_type]["file_name"])]
        )
        query_engine = self.index.as_query_engine(llm=self.llm, filters=filters)
        response = query_engine.query(map[memory_call_type]["query"](query_text))
        return response