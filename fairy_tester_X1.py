import asyncio
import os

from Citlali.core.runtime import CitlaliRuntime
from Fairy.config.fairy_config import FairyConfig
from Fairy.config.model_config import RAGChatModelConfig, RAGEmbedModelConfig, CoreChatModelConfig
from Fairy.memory.long_time_memory_manager import LongTimeMemoryManager, LongMemoryCallType
from Fairy.message_entity import CallMessage
from Fairy.type import CallType

os.environ["ADB_PATH"] = "C:/Users/neosunjz/AppData/Local/Android/Sdk/platform-tools/adb.exe"

class FairyTesterX1ForLongTimeMemory:
    def __init__(self, config):
        self.config = config

    async def start(self):
        runtime = CitlaliRuntime()
        runtime.run()
        runtime.register(lambda: LongTimeMemoryManager(runtime, self.config))

        # 从LongTimeMemoryManager获取Tips
        long_memory = await (await runtime.call(
            "LongTimeMemoryManager",
            CallMessage(CallType.Memory_GET, {
                LongMemoryCallType.GET_Plan_Tips: "请帮我在美团外卖App上点一个汉堡王的汉堡，当前的应用是就是美团外卖App",
            })
        ))
        self.instruction_tips = long_memory[LongMemoryCallType.GET_Plan_Tips]
        print(self.instruction_tips)
        await runtime.stop()

async def main():
    _config = FairyConfig(adb_path=os.environ["ADB_PATH"],
                          model=CoreChatModelConfig(
                              model_name="deepseek-v3-250324",  # "gpt-4o-2024-11-20"
                              model_temperature=0,
                              model_info={"vision": True, "function_calling": True, "json_output": True},
                              api_base="https://vip.apiyi.com/v1",
                              api_key="sk-8t4sGAakvPVKfFLn9801056499284a66B31aC07b1f9907F3"
                          ),
                          rag_model=RAGChatModelConfig(
                              model_name="qwen-long",
                              model_temperature=0,
                              api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
                              api_key="sk-d4e50bd7e07747b4827611c28da95c23"
                          ),
                          rag_embed_model=RAGEmbedModelConfig(
                              model_name="intfloat/multilingual-e5-large-instruct"
                          ),
                          non_visual_mode=True)
    fairy = FairyTesterX1ForLongTimeMemory(_config)
    await fairy.start()

if __name__ == '__main__':
    asyncio.run(main())