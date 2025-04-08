import os
import subprocess

from loguru import logger

from Citlali.core.runtime import CitlaliRuntime
from Citlali.models.openai.client import OpenAIChatClient
from Fairy.agents.app_executor_agent import AppExecutorAgent
from Fairy.agents.app_key_info_extractor_agent import KeyInfoExtractorAgent
from Fairy.agents.app_planner_agent import AppPlannerAgent
from Fairy.agents.user_interactor_agent import UserInteractorAgent
from Fairy.fairy_config import Config
from Fairy.memory.long_time_memory_manager import LongTimeMemoryManager
from Fairy.memory.short_time_memory_manager import ShortTimeMemoryManager
from Fairy.message_entity import EventMessage
from Fairy.tools.action_executor import ActionExecutor
from Fairy.tools.screen_perceptor import ScreenPerceptor
from Fairy.tools.task_manager import TaskManager
from Fairy.tools.user_chat import UserChat
from Fairy.type import EventType, EventStatus
from Fairy.utils.task_executor import TaskExecutor

os.environ["ADB_PATH"] = "C:/Users/neosunjz/AppData/Local/Android/Sdk/platform-tools/adb.exe"

class FairyCore:
    def __init__(self):
        self._model_client = OpenAIChatClient({
            'model': "gpt-4o-2024-11-20",
            'temperature': 0
        })
        # self._model_client = OpenAIChatClient({
        #     'model': "deepseek-v3",
        #     'model_info': {
        #         "vision": True,
        #         "function_calling": True,
        #         "json_output": True,
        #     },
        #     'temperature': 0
        # })

        self._config = Config(adb_path=os.environ["ADB_PATH"])

    async def get_device(self):
        async def _get_device():
            logger.info("[Get Device] TASK in progress...")
            result = subprocess.run(f"{os.environ['ADB_PATH']} devices", capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                device_strs = result.stdout.split("\n")
                devices = []
                for device_str in device_strs [1:]:
                    if "device" in device_str:
                        devices.append(device_str.split("\t")[0])
                return devices

        device_list = await TaskExecutor("Get_Screenshot", None).run(_get_device)
        print(device_list)
        if len(device_list) == 0:
            raise Exception("No device found.")
        elif len(device_list) > 1:
            raise Exception("Multiple devices found.")
        else:
            self._config.device = device_list[0]
            logger.info(f"[Get Device] TASK completed. Device: {self._config.device} has been set.")

    async def start(self, instruction):
        await self.get_device()

        runtime = CitlaliRuntime()
        runtime.run()
        runtime.register(lambda: AppPlannerAgent(runtime, self._model_client))
        runtime.register(lambda: AppExecutorAgent(runtime, self._model_client))
        runtime.register(lambda: ActionExecutor(runtime, self._config))
        runtime.register(lambda: ScreenPerceptor(runtime, self._config))
        runtime.register(lambda: KeyInfoExtractorAgent(runtime, self._model_client))
        runtime.register(lambda: UserInteractorAgent(runtime, self._model_client))
        runtime.register(lambda: UserChat(runtime))
        runtime.register(lambda: ShortTimeMemoryManager(runtime))
        runtime.register(lambda: LongTimeMemoryManager(runtime))
        runtime.register(lambda: TaskManager(runtime))

        await runtime.publish("app_channel", EventMessage(EventType.Task, EventStatus.CREATED, {
            "instruction": instruction
        }))
        await runtime.stop()