import json
import os
import re

from loguru import logger
from tqdm import tqdm

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.config.fairy_config import FairyConfig
from Fairy.entity.message_entity import EventMessage, CallMessage
from Fairy.tools.mobile_controller.action_type import AtomicActionType
from Fairy.entity.type import CallType
from google_play_scraper import app as get_app_info
from google_play_scraper.exceptions import NotFoundError

class AppInfoManager(Agent):
    def __init__(self, runtime, config: FairyConfig) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for retrieving, collecting & summarizing App Information.",
            type="SystemMessage")]
        super().__init__(runtime, "AppInfoManager", config.model_client, system_messages)

        self.manual_collect_app_info = config.manual_collect_app_info
        self.user_mobile_record_path = os.path.join(config.get_user_mobile_record_path(), "app_info.json")
        self.app_info_list = self.load_app_info_list()

    @listener(ListenerType.ON_CALLED, listen_filter=lambda message: message.call_type == CallType.App_Info_GET)
    async def get_app_info_list(self, message:EventMessage , message_context):
        logger.bind(log_tag="fairy_sys").debug("[AppInfo Get] TASK in progress...")

        current_package_list = await (await self.call(
            "ActionExecutor",
            CallMessage(CallType.Action_EXECUTE,{
                "atomic_action": AtomicActionType.ListApps,
                "args": {}
            })
        ))

        new_app_list, removed_app_list = self.check_difference(current_package_list)

        if len(new_app_list) > 0:
            logger.bind(log_tag="fairy_sys").debug(f"[AppInfo Get] New App List: {new_app_list}")

            if not self.manual_collect_app_info:
                logger.bind(log_tag="fairy_sys").warning(f"[Applnfo Get] We use the Google App Store to obtain information about apps.Due to regulatory restrictions, apps that are widely used in some regions (e.g. China) may not be available in the Google Play Store, which will make the information unavailable. If you need to improve the results manually, please configure 'manual_collect_app_info' in FairyConfig to True．")

                new_app_list_with_google_info = []
                for app_package_name in tqdm(new_app_list):
                    try:
                        result = get_app_info(
                            app_package_name,
                            lang='en',
                        )
                        new_app_list_with_google_info.append({
                            "app_package_name": app_package_name,
                            "app_name": result["title"],
                            "app_desc": result["description"]
                        })
                    except NotFoundError as e:
                        new_app_list_with_google_info.append({
                            "app_package_name": app_package_name,
                            "app_name": "UNKNOWN",
                            "app_desc": "UNKNOWN",
                        })
                llm_response = await self.request_llm(
                    self.build_prompt(
                        new_app_list_with_google_info,
                        True
                    )
                )
            else:
                logger.bind(log_tag="fairy_sys").warning(f"[Applnfo Get] Please send the input of the Prompt shown next to LLM that has an internet search (Highly Recommended: ChatGPT 4o / DeepSeek V3 with Search Turned on). Then send the Prompt input shown next to any model that has a network search, and finally paste the model's output here.")
                print(self.build_prompt(new_app_list))
                llm_response = ""
                while True:
                    line = input()
                    if line == "":
                        break
                    llm_response += line
                llm_response = json.loads(llm_response)
            for app_info in llm_response:
                self.app_info_list[app_info["app_package_name"]] = {
                    "app_name": app_info["app_name"].replace("\xa0", "\x20"),
                    "app_desc": app_info["app_desc"].replace("\xa0", "\x20")
                }

        if len(removed_app_list) > 0:
            logger.bind(log_tag="fairy_sys").debug(f"[AppInfo Get] Removed App List: {removed_app_list}")
            for app_package_name in removed_app_list:
                if self.app_info_list.get(app_package_name, None) is not None:
                    del self.app_info_list[app_package_name]

        if len(new_app_list) > 0 or len(removed_app_list) > 0:
            self.save_app_info_list()

        return self.app_info_list

    def check_difference(self, current_package_list):
        new_app_list = []
        removed_app_list =[]
        for app_package_name in current_package_list:
            if app_package_name not in self.app_info_list.keys():
                new_app_list.append(app_package_name)

        for app_package_name in self.app_info_list.keys():
            if app_package_name not in current_package_list:
                removed_app_list.append(app_package_name)

        return new_app_list, removed_app_list

    def load_app_info_list(self):
        # 判断文件是否存在
        if os.path.exists(self.user_mobile_record_path):
            with open(self.user_mobile_record_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {}

    def save_app_info_list(self):
        with open(self.user_mobile_record_path, 'w', encoding='utf-8') as f:
            # noinspection PyTypeChecker
            json.dump(self.app_info_list, f, ensure_ascii=False, indent=4)

    @staticmethod
    def build_prompt(app_info_list, is_manual_collect=False) -> str:
        prompt = f"---\n"
        if is_manual_collect:
            prompt += "Here are a series of package names and app names and descriptions from Google Play (Some app information may not exist, Please search for it). Organize the name of the application and a concise functional description: \n"
            for app_info in app_info_list:
                prompt += f"Package: {app_info['app_package_name']} | Title: {app_info['app_name']} | Desc: {app_info['app_desc']}\n"
        else:
            prompt += "Here are a series of package names. Search and Organize the name of the application and a concise functional description: \n"
            prompt += f"Package List: {app_info_list}\n"
        prompt += f"\n"\

        prompt += f"---\n"\
                  f"Please provide a JSON Array where each element is a JSON Object with 3 keys, which are interpreted as follows: \n"\
                  "- app_package_name: Fill in the package name directly. \n"\
                  "- app_name: Please fill in the app name, please make sure the information is real. If you can not determine the name please fill in UNKNOWN. \n"\
                  "- app_desc: Please fill in a short description of the app's features, make sure the information is true, if you are not sure about the app description please fill in UNKNOWN. \n"\
                  f"Make sure this JSON can be loaded correctly by json.load().\n"
        return prompt

    def parse_response(self, response: str) -> list:
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        return json.loads(response)