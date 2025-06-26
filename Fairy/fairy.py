import os
import re
import subprocess
import sys
import time

from loguru import logger

from Citlali.core.runtime import CitlaliRuntime
from Fairy.agents.app_executor_agents.app_action_decider_agent import AppActionDeciderAgent
from Fairy.agents.app_executor_agents.app_key_info_extractor_agent import KeyInfoExtractorAgent
from Fairy.agents.app_executor_agents.app_planner_agent.app_planner_agent import AppPlannerAgent
from Fairy.agents.app_executor_agents.app_planner_agent.app_reflector_agent import AppReflectorAgent
from Fairy.agents.app_executor_agents.app_planner_agent.app_replanner_for_act_exec import AppRePlannerForActExecAgent
from Fairy.agents.app_executor_agents.app_planner_agent.app_replanner_for_usr_chat import AppRePlannerForUsrChatAgent
from Fairy.agents.global_planner_agents.global_planner_agent import GlobalPlannerAgent
from Fairy.agents.app_executor_agents.user_interactor_agent import UserInteractorAgent
from Fairy.agents.global_planner_agents.global_replanner_agent import GlobalRePlannerAgent
from Fairy.config.fairy_config import FairyConfig
from Fairy.fairy_recovery import FairyRecovery
from Fairy.memory.long_time_memory_manager import LongTimeMemoryManager
from Fairy.memory.short_time_memory_manager import ShortTimeMemoryManager
from Fairy.entity.message_entity import EventMessage
from Fairy.tools.mobile_controller.action_executor import ActionExecutor
from Fairy.tools.app_info_manager import AppInfoManager
from Fairy.tools.screen_perceptor.screen_perceptor import ScreenPerceptor
from Fairy.tools.task_manager import TaskManager
from Fairy.tools.user_dialoger import UserDialoger
from Fairy.entity.type import EventType, EventStatus, EventChannel
from Fairy.utils.task_executor import TaskExecutor

class FairyCore:
    def __init__(self, config:FairyConfig):
        self._config = config

    async def get_device(self):
        async def _get_device():
            logger.bind(log_tag="fairy_sys").info("Getting currently available devices...")
            result = subprocess.run(f"{os.environ['ADB_PATH']} devices", capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                device_strs = result.stdout.split("\n")
                devices = []
                for device_str in device_strs [1:]:
                    if "device" in device_str:
                        devices.append(device_str.split("\t")[0])
                return devices

        device_list = await TaskExecutor("Get_Device", None).run(_get_device)
        logger.bind(log_tag="fairy_sys").info("The following available devices have been found: " + ','.join(map(str, device_list)))

        if len(device_list) == 0:
            raise Exception("No available device found.")

        if self._config.device is not None:
            if self._config.device not in device_list:
                raise Exception("The device specified in the configuration is not available.")
            else:
                return
        else:
            if len(device_list) > 1:
                raise Exception("Multiple devices found. Please specify the device in the configuration.")
            else:
                self._config.device = device_list[0]
                logger.bind(log_tag="fairy_sys").info(f"Since the device is not specified in the configuration, device {self._config.device} has been set.")

    async def new_task(self, task_name="Unnamed"):
        # 新建任务临时文件夹
        current_time = time.strftime("%Y%m%d%H%M%S", time.localtime())
        task_temp_path = f"{self._config.temp_path}/{task_name}_{current_time}"
        os.mkdir(task_temp_path)
        self._config.task_temp_path = task_temp_path

        # 新建文件夹
        os.mkdir(self._config.get_screenshot_temp_path())
        os.mkdir(self._config.get_log_temp_path())
        os.mkdir(self._config.get_restore_point_path())

        # 配置全局日志
        logger.remove(0)
        logger.add(sink=sys.stdout, level="INFO", colorize=True, filter=lambda x: (x["extra"].get("log_tag") == "citlali_sys"))
        logger.add(sink=sys.stdout, level="DEBUG", colorize=True, filter=lambda x: (x["extra"].get("log_tag") == "fairy_sys"))

        remove_ansi = lambda record: not record.update({"message": re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]').sub('', record["message"])}) or True

        logger.add(self._config.get_log_temp_path() + "/fairy_sys_log.log", filter=lambda x: x["extra"].get("log_tag") == "fairy_sys" and remove_ansi(x), format="{message}", level="DEBUG")
        logger.add(self._config.get_log_temp_path() + "/citlali_sys_log.log", filter=lambda x: x["extra"].get("log_tag") == "citlali_sys", level="DEBUG")
        logger.add(self._config.get_log_temp_path() + "/agent_res&req_log.log", filter=lambda x: x["extra"].get("log_tag") in ["agent_req", "agent_res"], level="DEBUG")
        logger.add(self._config.get_log_temp_path() + "/screen_perception_log.log", filter=lambda x: x["extra"].get("log_tag") == "screen_perception", level="DEBUG")

    async def start(self, instruction, task_name="Unnamed"):
        print("    ______      _           \n"
              "   / ____/___ _(_)______  __\n"
              "  / /_  / __ `/ / ___/ / / /\n"
              " / __/ / /_/ / / /  / /_/ / \n"
              "/_/    \__,_/_/_/   \__, /  \n"
              "                   /____/   \n"
              )
        print("Fairy Mobile Assistant V1.5.3 (Fairy Next) \n"
              "[Design BY Jiazheng.Sun, Te.Yang, Jiayang.Niu, Yongyong.Lu] \n"
              "[Fudan University CodeWisdom Lab © 2025]\n")
        await self.new_task(task_name)
        await self.get_device()

        runtime = CitlaliRuntime()
        runtime.run()
        runtime.register(lambda: GlobalPlannerAgent(runtime, self._config))
        runtime.register(lambda: GlobalRePlannerAgent(runtime, self._config))

        runtime.register(lambda: AppPlannerAgent(runtime, self._config))
        runtime.register(lambda: AppReflectorAgent(runtime, self._config))
        runtime.register(lambda: AppRePlannerForActExecAgent(runtime, self._config))
        runtime.register(lambda: AppRePlannerForUsrChatAgent(runtime, self._config))
        runtime.register(lambda: AppActionDeciderAgent(runtime, self._config))
        runtime.register(lambda: KeyInfoExtractorAgent(runtime, self._config))
        runtime.register(lambda: UserInteractorAgent(runtime, self._config))

        runtime.register(lambda: ActionExecutor(runtime, self._config))
        runtime.register(lambda: ScreenPerceptor(runtime, self._config))
        runtime.register(lambda: AppInfoManager(runtime, self._config))
        runtime.register(lambda: UserDialoger(runtime, self._config))

        runtime.register(lambda: ShortTimeMemoryManager(runtime, self._config))
        runtime.register(lambda: LongTimeMemoryManager(runtime, self._config))

        runtime.register(lambda: FairyRecovery(runtime, self._config))

        runtime.register(lambda: TaskManager(runtime))
        await runtime.publish(EventChannel.GLOBAL_CHANNEL, EventMessage(EventType.INIT, EventStatus.CREATED, {
            "user_instruction": instruction
        }))

        await runtime.stop()