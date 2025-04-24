import asyncio
import os

from Citlali.core.runtime import CitlaliRuntime
from Fairy.agents.global_planner import GlobalPlannerAgent
from Fairy.config.model_config import CoreChatModelConfig, RAGChatModelConfig, RAGEmbedModelConfig
from Fairy.fairy import FairyCore
from Fairy.config.fairy_config import FairyConfig
from Fairy.message_entity import EventMessage
from Fairy.tools.mobile_controller.action_executor import ActionExecutor
from Fairy.tools.mobile_controller.app_info_manager import AppInfoManager
from Fairy.type import EventType, EventStatus

ADB_PATH = "C:/Users/neosunjz/AppData/Local/Android/Sdk/platform-tools/adb.exe"

async def main():
    _config = FairyConfig(adb_path=os.environ["ADB_PATH"],
                          model=CoreChatModelConfig(
                              model_name="deepseek-v3-250324", # "gpt-4o-2024-11-20"
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
                          non_visual_mode=True,
                          manual_collect_app_info=True
                          )
    fairy = FairyCore(_config)
    await fairy.new_task("TestX2")
    await fairy.get_device()

    runtime = CitlaliRuntime()
    runtime.run()
    runtime.register(lambda: AppInfoManager(runtime, fairy._config))
    runtime.register(lambda: GlobalPlannerAgent(runtime, fairy._config))
    runtime.register(lambda: ActionExecutor(runtime, fairy._config))

    await runtime.publish("app_channel", EventMessage(EventType.GlobalPlan, EventStatus.CREATED, {
        "user_instruction": "在地图上为我找附件的一家受欢迎的川菜馆。查看相关评价，并帮我总结到记事本里。最后帮我导航到这家餐厅"
    }))
    await runtime.stop()

if __name__ == '__main__':
    asyncio.run(main())