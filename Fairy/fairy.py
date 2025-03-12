import os

from Citlali.core.runtime import CitlaliRuntime
from Citlali.models.openai.client import OpenAIChatClient
from Fairy.agents.app_executor_agent import AppExecutorAgent
from Fairy.agents.app_planner_agent import AppPlannerAgent
from Fairy.agents.app_reflector_agent import AppReflectorAgent
from Fairy.fairy_config import Config
from Fairy.tools.operation_execution import OperationExecution
from Fairy.tools.screen_perception import ScreenPerception

os.environ["OPENAI_API_KEY"] = "sk-8t4sGAakvPVKfFLn9801056499284a66B31aC07b1f9907F3"
os.environ["OPENAI_BASE_URL"] = "https://vip.apiyi.com/v1"

class FairyCore:
    def __init__(self):
        self._model_client = OpenAIChatClient({
            'model': "gpt-4o-2024-11-20"
        })
        self._config = Config(adb_path="")

    async def start(self):
        runtime = CitlaliRuntime()
        runtime.run()
        runtime.register(lambda: AppPlannerAgent(runtime, self._model_client))
        runtime.register(lambda: AppExecutorAgent(runtime, self._model_client))
        runtime.register(lambda: AppReflectorAgent(runtime, self._model_client))
        runtime.register(lambda: OperationExecution(runtime, self._config))

        await runtime.publish("test_channel", "TestPublishMessage!")
        await runtime.stop()