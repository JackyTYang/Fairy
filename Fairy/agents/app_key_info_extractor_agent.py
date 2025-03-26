import json
import re

from loguru import logger

from Citlali.core.agent import Agent
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Citlali.models.entity import ChatMessage
from Fairy.info_entity import PlanInfo, ProgressInfo, ScreenPerceptionInfo, ActionInfo
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventType, EventStatus, CallType, MemoryType


class KeyInfoExtractorAgent(Agent):
    def __init__(self, runtime, model_client) -> None:
        system_messages = [ChatMessage(
            content="You are a helpful AI assistant for operating mobile phones. Your goal is to take notes of important content relevant to the user's request.",
            type="SystemMessage")]
        super().__init__(runtime, "KeyInfoExtractorAgent", model_client, system_messages)

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.Plan and msg.status == EventStatus.DONE)
    async def on_key_info_extract(self, message:EventMessage , message_context):
        logger.debug("[KeyInfoExtract] TASK in progress...")

        # 从ShortTimeMemoryManager获取Instruction, CurrentScreenPerception, Plan
        memory = await self.call("ShortTimeMemoryManager", CallMessage(CallType.Memory_GET, [MemoryType.Instruction, MemoryType.ActionResult, MemoryType.KeyInfo, MemoryType.ScreenPerception]))
        memory = await memory
        # 构建Prompt
        key_info_extraction_event_content = await self.request_llm(
            self.build_prompt(
                memory[MemoryType.Instruction], # Instruction
                message.event_content,  # PlanInfo
                # ProgressInfoList can be empty if this is the first reflection
                memory[MemoryType.ActionResult][-1] if len(memory[MemoryType.ActionResult]) > 0 else None, # ProgressInfo
                memory[MemoryType.KeyInfo], # KeyInfoList
                memory[MemoryType.ScreenPerception][-1], # CurrentScreenPerceptionInfo
            ),
            [
                memory[MemoryType.ScreenPerception][-1].screenshot_file_info.get_screenshot_Image_file(), # CurrentScreenImageFile
            ]
        )

        # 发布Plan事件
        await self.publish("app_channel", EventMessage(EventType.KeyInfoExtraction, EventStatus.DONE, key_info_extraction_event_content))
        logger.info("[KeyInfoExtract] TASK completed.")

    @staticmethod
    def build_prompt(instruction,
                     plan_info: PlanInfo,
                     progress_info: ProgressInfo,
                     key_infos: list,
                     current_screen_perception_info: ScreenPerceptionInfo) -> str:
        prompt = f"---\n"\
                 f"The Executor Agent has just completed execution according to the Planner Agent's plan and the result was successful/partially successful, which is the instruction, overall plan, sub-goals, and historical progress:\n"

        prompt += f"- Instruction: {instruction}\n"\
                  f"- Overall Plan: {plan_info.overall_plan}\n" \
                  f"- Sub-goal: {plan_info.current_sub_goal}\n" \
                  f"- History Progress Status: {progress_info.progress_status if progress_info is not None else 'No progress yet.'}\n" \

        prompt += f"---\n"
        prompt += current_screen_perception_info.perception_infos.get_screen_info_note_prompt("The attached image is a screenshots of your phone to show the current state") # Call this function to supplement the prompt "Size of the Image and Additional Information".
        prompt += f"\n"

        prompt += current_screen_perception_info.perception_infos.get_screen_info_prompt() # Call this function to get the content of the prompt "Screen Perception Information and Keyboard Status".

        prompt += f"---\n"\
                  f" - Key Information Record (Previously): {key_infos}\n" \
                  f"Please follow the steps below to perform the action:\n"\
                  "1. Please scrutinize the above information and extract any 'Key Information' that you think may be relevant to the execution of the instruction, the current sub-goal, or a future plan. This 'Key Information' will be subsequently provided to the planner and executor for their reference. \n"\
                  "IMPORTANT: DO NOT duplicate any information that already exists in the Instruction, Overall Plan, Sub-goals, and Historical Progress. DO NOT record low-level actions.\n"\
                  "IMPORTANT: If there really is no key information worth recording or updating, please just output the previous 'Key Information' and skip the subsequent steps. \n" \
                  "For example, for a search task, the result information displayed after the search is the 'Key Information'.\n"\
                  "2. Please use JSON to format the relevant 'Key Information': think step-by-step to summarize the keys of the JSON, and split the key information to fill in the values of the JSON. \n"\
                  "For example, if the search results contain titles, contents, etc., the two Keys 'title' and 'content' should be summarized, and the specific title and content should be filled in. \n"\
                  "3. When there are multiple key information of the same type, it should be merged into an array.\n"\
                  "For example, [{'title':... , 'content':...} ,{'title':... , 'content':...} ,...]\n"\
                  "4. If there are records of the same type as the currently recorded key information in the previous 'Key Information Record', they should be merged into the 'details' array of the previous record; otherwise, a new 'Key Information Record' should be added.\n"\

        prompt += f"---\n"\
                  f"The 'Key Information Record' is a JSON with 3 keys, which are interpreted as follows:\n"\
                  f"- key_info_name: Summarizes the subject of this 'Key Information'. e.g. results of a certain search content.\n"\
                  f"- key_info_description: Explain in detail what the 'Key Information' is, and the purpose of recording this.\n"\
                  f"- details: An array holding one or more JSON formatted 'Key Information'.\n"\
                  f"Please provide an array that holds one or more 'Key Information Record's. This array should contain updates to previous 'Key Information Record's, please do not leave out records that already exist.\n"\
                  f"Make sure this JSON can be loaded correctly by json.load().\n"\
                  f"\n"

        return prompt

    def parse_response(self, response: str) -> list:
        if "json" in response:
            response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
        key_infos = json.loads(response)
        return key_infos
