import asyncio

from loguru import logger

from Citlali.core.type import ListenerType
from Citlali.core.worker import Worker, listener
from Fairy.info_entity import UserInteractionInfo
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.type import EventType, EventStatus, CallType, MemoryType


class ShortTimeMemoryManager(Worker):
    def __init__(self, runtime):
        super().__init__(runtime, "ShortTimeMemoryManager", "ShortTimeMemoryManager")
        self.memory_list = {}
        self.current_memory = {
            MemoryType.Instruction: {
                "ori": None,
                "updated": []
            },
            MemoryType.Plan: [],
            MemoryType.ScreenPerception: [],
            MemoryType.Action: [],
            MemoryType.ActionResult: [],
            MemoryType.KeyInfo: [],
            MemoryType.UserInteraction: [],
        } # 暂时只有一个短时记忆，暂未考虑多个短时记忆的情况

        self.memory_ready_event = {}
        self.allow_empty_list = [MemoryType.Action, MemoryType.ActionResult, MemoryType.KeyInfo, MemoryType.UserInteraction]

    async def _get_memory(self, memory_type):
        def _get_memory_by_type(memory_type):
            _memory = self.current_memory.get(memory_type)
            match memory_type:
                case MemoryType.Instruction:
                    if _memory["ori"] is None:
                        return None
                    # 如果是指令记忆，需要将用户交互后的指令加入到记忆中
                    return _memory["ori"] + (f"Instructions added after user interaction: {','.join(_memory['updated'])}" if len(_memory["updated"]) > 0 else "")
                case _:
                    return _memory

        memory = _get_memory_by_type(memory_type)
        if memory_type not in self.allow_empty_list and (memory is None or memory == []):
            self.memory_ready_event[memory_type] = asyncio.Event()
            # 等待记忆被提供
            logger.debug(f"Waiting for memory {memory_type} to provide.")
            await self.memory_ready_event[memory_type].wait()
            self.memory_ready_event.pop(memory_type)
            # 重新获取记忆
            memory = _get_memory_by_type(memory_type)
        return memory

    async def set_memory_ready(self, memory_type):
        if memory_type in self.memory_ready_event:
            # 通知等待记忆提供的任务
            self.memory_ready_event[memory_type].set()

    @listener(ListenerType.ON_CALLED, listen_filter=lambda message: message.call == CallType.Memory_GET)
    async def get_memory(self, message: CallMessage, message_context):
        memory = {}
        for memory_type in message.call_content:
            memory[memory_type] = await self._get_memory(memory_type)
        return memory

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.Plan and message.status == EventStatus.CREATED)
    async def set_instruction_memory(self, message: EventMessage, message_context):
        self.current_memory[MemoryType.Instruction]["ori"] = message.event_content
        await self.set_memory_ready(MemoryType.Plan)

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.UserInteraction and message.status == EventStatus.DONE)
    async def update_instruction_memory(self, message: EventMessage, message_context):
        self.current_memory[MemoryType.Instruction]["updated"].append(message.event_content.user_response)

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel")
    async def set_memory(self, message: EventMessage, message_context):
        memory_type_conversion_list = {
            EventType.Plan: {
                EventStatus.DONE: MemoryType.Plan
            },
            EventType.ScreenPerception: {
                EventStatus.DONE: MemoryType.ScreenPerception
            },
            EventType.ActionExecution: {
                EventStatus.DONE: MemoryType.Action
            },
            EventType.Reflection: {
                EventStatus.DONE: MemoryType.ActionResult
            },
            EventType.KeyInfoExtraction: {
                EventStatus.DONE: MemoryType.KeyInfo
            },
            EventType.UserInteraction: {
                EventStatus.DONE: MemoryType.UserInteraction
            },
            EventType.UserChat: {
                EventStatus.DONE: MemoryType.UserInteraction
            }
        }
        memory_type = memory_type_conversion_list.get(message.event, []).get(message.status, None)
        if memory_type is None:
            return
        self.current_memory[memory_type].append(message.event_content)
        await self.set_memory_ready(memory_type)
    #
    # @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
    #           listen_filter=lambda message: message.event == EventType.ScreenPerception and message.status == EventStatus.DONE)
    # async def set_screen_perception_memory(self, message: EventMessage, message_context):
    #     self.current_memory[MemoryType.ScreenPerception].append(message.event_content)
    #     await self.set_memory_ready(MemoryType.ScreenPerception)
    #
    # @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
    #           listen_filter=lambda message: message.event == EventType.Plan and message.status == EventStatus.DONE)
    # async def set_plan_memory(self, message: EventMessage, message_context):
    #     self.current_memory[MemoryType.Plan].append(message.event_content)
    #     await self.set_memory_ready(MemoryType.Plan)
    #
    # @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
    #           listen_filter=lambda message: message.event == EventType.Reflection and message.status == EventStatus.DONE)
    # async def set_action_result_memory(self, message: EventMessage, message_context):
    #     self.current_memory[MemoryType.ActionResult].append(message.event_content)
    #     await self.set_memory_ready(MemoryType.ActionResult)
    #
    # @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
    #           listen_filter=lambda message: message.event == EventType.ActionExecution and message.status == EventStatus.DONE)
    # async def set_action_memory(self, message: EventMessage, message_context):
    #     self.current_memory[MemoryType.Action].append(message.event_content)
    #     await self.set_memory_ready(MemoryType.Action)
    #
    # @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
    #           listen_filter=lambda message: message.event == EventType.KeyInfoExtraction and message.status == EventStatus.DONE)
    # async def set_key_info_memory(self, message: EventMessage, message_context):
    #     self.current_memory[MemoryType.KeyInfo] = message.event_content
    #     await self.set_memory_ready(MemoryType.KeyInfo)
    #
    # @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
    #           listen_filter=lambda message: (message.event == EventType.UserInteraction or message.event == EventType.UserChat)
    #           and message.status == EventStatus.DONE)
    # async def set_user_interaction_memory(self, message: EventMessage, message_context):
    #     self.current_memory[MemoryType.UserInteraction].append(message.event_content)
    #     await self.set_memory_ready(MemoryType.UserInteraction)