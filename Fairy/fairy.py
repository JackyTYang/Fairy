import os

from Citlali.core.runtime import CitlaliRuntime
from Citlali.models.openai.client import OpenAIChatClient
from Fairy.agents.app_executor_agent import AppExecutorAgent
from Fairy.agents.app_planner_agent import AppPlannerAgent
from Fairy.agents.app_reflector_agent import AppReflectorAgent
from Fairy.fairy_config import Config
from Fairy.memory.short_time_memory_manger import ShortTimeMemoryManager
from Fairy.message_entity import EventMessage
from Fairy.tools.operation_execution import OperationExecution
from Fairy.tools.screen_perception import ScreenPerception
from Fairy.type import EventType, EventStatus

os.environ["OPENAI_API_KEY"] = "sk-8t4sGAakvPVKfFLn9801056499284a66B31aC07b1f9907F3"
os.environ["OPENAI_BASE_URL"] = "https://vip.apiyi.com/v1"

class FairyCore:
    def __init__(self):
        self._model_client = OpenAIChatClient({
            'model': "gpt-4o-2024-11-20"
        })
        self._config = Config(adb_path="C:/Users/neosunjz/AppData/Local/Android/Sdk/platform-tools/adb.exe")

    async def start(self, instruction):
        runtime = CitlaliRuntime()
        runtime.run()
        runtime.register(lambda: AppPlannerAgent(runtime, self._model_client))
        runtime.register(lambda: AppExecutorAgent(runtime, self._model_client))
        runtime.register(lambda: AppReflectorAgent(runtime, self._model_client))
        runtime.register(lambda: OperationExecution(runtime, self._config))
        runtime.register(lambda: ScreenPerception(runtime, self._config))
        runtime.register(lambda: ShortTimeMemoryManager(runtime))

        await runtime.publish("app_channel", EventMessage(EventType.Plan, EventStatus.CREATED, instruction))
        await runtime.stop()