import os
import subprocess
import sys
import time

from loguru import logger

from Citlali.core.runtime import CitlaliRuntime
from Fairy.agents.app_executor_agent import AppExecutorAgent
from Fairy.agents.app_key_info_extractor_agent import KeyInfoExtractorAgent
from Fairy.agents.app_planner_agent import AppPlannerAgent
from Fairy.agents.user_interactor_agent import UserInteractorAgent
from Fairy.fairy_config import FairyConfig
from Fairy.memory.long_time_memory_manager import LongTimeMemoryManager
from Fairy.memory.short_time_memory_manager import ShortTimeMemoryManager
from Fairy.message_entity import EventMessage
from Fairy.tools.mobile_controller.action_executor import ActionExecutor
from Fairy.tools.screen_perceptor.screen_perceptor import ScreenPerceptor
from Fairy.tools.task_manager import TaskManager
from Fairy.tools.user_chat import UserChat
from Fairy.type import EventType, EventStatus
from Fairy.utils.task_executor import TaskExecutor

os.environ["ADB_PATH"] = "C:/Users/neosunjz/AppData/Local/Android/Sdk/platform-tools/adb.exe"

class FairyCore:
    def __init__(self, config:FairyConfig):
        self._config = config

    async def get_device(self):
        async def _get_device():
            logger.bind(log_tag="fairy_sys").info("[Get Device] TASK in progress...")
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
            logger.bind(log_tag="fairy_sys").info(f"[Get Device] TASK completed. Device: {self._config.device} has been set.")

    async def new_task(self, task_name="Unnamed"):
        # 新建任务临时文件夹
        current_time = time.strftime("%Y%m%d%H%M%S", time.localtime())
        task_temp_path = f"{self._config.temp_path}/{task_name}_{current_time}"
        os.mkdir(task_temp_path)
        self._config.temp_path = task_temp_path

        # 新建文件夹
        os.mkdir(self._config.get_screenshot_temp_path())
        os.mkdir(self._config.get_log_temp_path())

        # 配置全局日志
        logger.remove(0)
        logger.add(sink=sys.stdout, level="DEBUG", colorize=True, filter=lambda x: (x["extra"].get("log_tag") == "fairy_sys" or x["extra"].get("log_tag") == "citlali_sys"))
        logger.add(self._config.get_log_temp_path() + "/fairy_sys_log.log", filter=lambda x: x["extra"].get("log_tag") == "fairy_sys", level="DEBUG")
        logger.add(self._config.get_log_temp_path() + "/citlali_sys_log.log", filter=lambda x: x["extra"].get("log_tag") == "citlali_sys", level="DEBUG")
        logger.add(self._config.get_log_temp_path() + "/agent_res&req_log.log", filter=lambda x: x["extra"].get("log_tag") == "agent_req&res", level="DEBUG")
        logger.add(self._config.get_log_temp_path() + "/screen_perception_log.log", filter=lambda x: x["extra"].get("log_tag") == "screen_perception", level="DEBUG")

    async def start(self, instruction, task_name="Unnamed"):
        print("    ______      _           \n"
              "   / ____/___ _(_)______  __\n"
              "  / /_  / __ `/ / ___/ / / /\n"
              " / __/ / /_/ / / /  / /_/ / \n"
              "/_/    \__,_/_/_/   \__, /  \n"
              "                   /____/   \n"
              )
        print("Fairy Mobile Assistant V0.1.9 \n"
              "[Design BY Jiazheng.Sun, Te.Yang, Jiayang.Niu, Yongyong.Lu] \n"
              "[Fudan University CodeWisdom Lab © 2025]\n")
        await self.new_task(task_name)
        await self.get_device()

        runtime = CitlaliRuntime()
        runtime.run()
        runtime.register(lambda: AppPlannerAgent(runtime, self._config))
        runtime.register(lambda: AppExecutorAgent(runtime, self._config))
        runtime.register(lambda: ActionExecutor(runtime, self._config))
        runtime.register(lambda: ScreenPerceptor(runtime, self._config))
        runtime.register(lambda: KeyInfoExtractorAgent(runtime, self._config))
        runtime.register(lambda: UserInteractorAgent(runtime, self._config))
        runtime.register(lambda: UserChat(runtime))
        runtime.register(lambda: ShortTimeMemoryManager(runtime))
        runtime.register(lambda: LongTimeMemoryManager(runtime))
        runtime.register(lambda: TaskManager(runtime))
        await runtime.publish("app_channel", EventMessage(EventType.Task, EventStatus.CREATED, {
            "instruction": instruction
        }))
        await runtime.stop()