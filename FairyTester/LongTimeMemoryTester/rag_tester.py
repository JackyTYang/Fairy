import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from Citlali.core.runtime import CitlaliRuntime
from Fairy.config.fairy_config import FairyConfig
from Fairy.config.model_config import RAGChatModelConfig, RAGEmbedModelConfig
from Fairy.memory.long_time_memory_manager import LongTimeMemoryManager, LongMemoryCallType, LongMemoryType
from Fairy.entity.message_entity import CallMessage
from Fairy.entity.type import CallType

load_dotenv(dotenv_path=Path('../.env'))

async def test():
    _config = FairyConfig(model = None,
                          rag_model=RAGChatModelConfig(
                              model_name="qwen-turbo-0428",
                              model_temperature=0,
                              api_base=os.getenv("ALI_API_BASE"),
                              api_key=os.getenv("ALI_API_KEY")
                          ),
                          rag_embed_model=RAGEmbedModelConfig(
                              model_name="intfloat/multilingual-e5-large-instruct"
                          ),
                          visual_prompt_model= None,
                          text_summarization_model= None,
                          adb_path = "C:/Users/neosunjz/AppData/Local/Android/Sdk/platform-tools/adb.exe",
                          temp_path=None)

    runtime = CitlaliRuntime()
    runtime.run()
    runtime.register(lambda: LongTimeMemoryManager(runtime, _config))

    # 从LongTimeMemoryManager获取Tips
    long_memory = await (await runtime.call(
        "LongTimeMemoryManager",
        CallMessage(CallType.Memory_GET, {
            LongMemoryCallType.GET_Tips: {
                LongMemoryType.Execution_Tips: {
                    "query": "2. Locate the subsection containing Filet-O-Fish (麦香鱼汉堡) from the menu.",
                    "app_package_name": "com.mcdonalds.gma.cn"
                }
            }
        })
    ))

    instruction_tips = long_memory[LongMemoryCallType.GET_Tips][LongMemoryType.Execution_Tips]
    print(instruction_tips)
    await runtime.stop()

if __name__ == '__main__':
    asyncio.run(test())