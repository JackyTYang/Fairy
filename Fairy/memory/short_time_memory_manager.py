import asyncio
from enum import Enum
from Citlali.core.type import ListenerType
from Citlali.core.worker import Worker, listener
from Fairy.info_entity import ActionInfo, ProgressInfo, UserInteractionInfo
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.tools.action_type import AtomicActionType
from Fairy.type import EventType, EventStatus, CallType
from loguru import logger

class MemoryType(Enum):
    Instruction = 0
    Actions = 1
    UserInteraction = 2
    KeyInfo = 3


class ActionMemoryType(Enum):
    StartScreenPerception = 1
    Plan = 2
    Action = 3
    ActionResult = 4
    EndScreenPerception = 5

class MemoryCallType(Enum):
    GET_Instruction = 1
    GET_Current_Action_Memory = 2
    GET_Historical_Action_Memory = 3
    GET_Is_INIT_MODE = 4
    GET_Key_Info = 5
    GET_Current_User_Interaction = 6

class ShortTimeMemoryManager(Worker):
    def __init__(self, runtime):
        super().__init__(runtime, "ShortTimeMemoryManager", "ShortTimeMemoryManager")
        self.memory_list = []
        self.old_memory_list = []

        self.task_name = None
        self.current_memory = None
        self.current_memory_ready_event = None

    def new_memory(self, task_name=None):
        self.task_name = task_name
        self.current_memory = {
            MemoryType.Instruction: {
                "ori": None,
                "updated": [],
                "thought": None,
            },
            MemoryType.Actions: [],
            MemoryType.KeyInfo:[],
            MemoryType.UserInteraction: [],
            "init_mode": False
        } # 暂时只有一个短时记忆，暂未考虑多个短时记忆的情况
        self.current_memory_ready_event = {}

    def push_task_memory(self, task_name):
        self.memory_list.append({
            "task_name": self.task_name,
            "memory": self.current_memory,
            "memory_ready_event": self.current_memory_ready_event,
        }) # 保存当前短时记忆
        # 新建一个短时记忆
        self.new_memory(task_name)

    def pop_task_memory(self):
        self.old_memory_list.append({
            "task_name": self.task_name,
            "memory": self.current_memory,
            "memory_ready_event": self.current_memory_ready_event,
        }) # 保存当前短时记忆到历史记忆
        # 恢复上一个短时记忆
        last_memory = self.memory_list.pop()
        if len(self.memory_list) > 0:
            self.task_name = last_memory["task_name"]
            self.current_memory = last_memory["memory"]
            self.current_memory_ready_event = last_memory["memory_ready_event"]
            return self.old_memory_list[-1]
        else:
            raise Exception("No memory to pop.")

    @listener(ListenerType.ON_CALLED, listen_filter=lambda message: message.call_type == CallType.Memory_SWITCH)
    async def switch_task_memory(self, message: CallMessage, message_context):
        return self.pop_task_memory()

    def add_action(self):
        self.current_memory[MemoryType.Actions].append({
            ActionMemoryType.StartScreenPerception: None,
            ActionMemoryType.Plan: None,
            ActionMemoryType.Action: None,
            ActionMemoryType.EndScreenPerception: None,
            ActionMemoryType.ActionResult: None,
        })

    async def next_action(self):
        # 下一个Action的StartScreenPerception记忆是上一个Action的EndScreenPerception记忆
        next_start_screen_perception = (await self._get_current_action_memory([ActionMemoryType.EndScreenPerception]))[
            ActionMemoryType.EndScreenPerception]
        # 新增一个Action
        self.add_action()
        # 设置下一个Action的StartScreenPerception记忆
        await self._set_current_action_memory(ActionMemoryType.StartScreenPerception, next_start_screen_perception)

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.Task and message.status == EventStatus.CREATED)
    async def create_task_memory(self, message: EventMessage, message_context):
        if len(self.memory_list) == 0 and self.current_memory is None:
            self.new_memory("Main Task") # 初始化短时记忆(Main Task)
        else:
            self.push_task_memory("Sub-Task:"+ message.event_content.get("task_name", "no_named_task")) # 保存当前短时记忆

        # 设为初始化模式
        self.current_memory["init_mode"] = True
        # 新增一个Action
        self.add_action()
        # 设置最初的用户指示
        self.current_memory[MemoryType.Instruction]["ori"] = message.event_content.get("instruction")
        self.current_memory[MemoryType.Instruction]["thought"] = message.event_content.get("thought", None)
        await self.set_memory_ready(MemoryType.Instruction)

    # 当event为UserInteraction时，更新当前Instruction的记忆
    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.UserInteraction and message.status == EventStatus.DONE)
    async def update_instruction_memory(self, message: EventMessage, message_context):
        self.current_memory[MemoryType.Instruction]["updated"].append(message.event_content.response)
        # 构建本次的Action
        self.current_memory[MemoryType.Actions][-1][ActionMemoryType.Action] = ActionInfo(
            "User Instruction", [{"name": AtomicActionType.UserInstruction}], "Get Responses."
        )
        self.current_memory[MemoryType.Actions][-1][ActionMemoryType.ActionResult] = ProgressInfo(
            "A", None, None
        )
        # 用户询问轮，屏幕信息不发生变化
        self.current_memory[MemoryType.Actions][-1][ActionMemoryType.EndScreenPerception] = self.current_memory[MemoryType.Actions][-1][ActionMemoryType.StartScreenPerception]

    # 当event为UserChat时，更新当前UserInteraction的记忆
    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.UserChat and message.status == EventStatus.DONE)
    async def update_current_user_interaction_memory(self, message: EventMessage, message_context):
        self.current_memory[MemoryType.UserInteraction][-1].append(message.event_content)

    # 当event为TaskFinish时，按情况处理
    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.TaskFinish and message.status == EventStatus.DONE)
    async def on_task_finish_update_memory(self, message: EventMessage, message_context):
        content_type = type(message.event_content)
        if content_type is UserInteractionInfo:
            # 如果是用户交互，更新当前UserInteraction的记忆
            await self.update_current_user_interaction_memory(message, message_context)
        else:
            raise Exception("Unknown event content type.")


    # 当event为Plan、ActionExecution、ScreenPerception、Reflection时，更新当前Action的记忆
    @listener(ListenerType.ON_NOTIFIED, channel="app_channel", listen_filter=lambda message:(message.event == EventType.Plan or message.event == EventType.ActionExecution or message.event == EventType.ScreenPerception or message.event == EventType.Reflection) and message.status == EventStatus.DONE)
    async def set_current_action_memory(self, message: EventMessage, message_context):
        match message.event:
            case EventType.Plan:
                # 如果是初始化模式，切换到非初始化模式
                if self.current_memory["init_mode"]:
                    self.current_memory["init_mode"] = False
                else:
                    await self.next_action()
                if message.event_content.user_interaction_type != 0:
                    # 如果当前Plan需要用户交互，则新增新的UserInteraction
                    self.current_memory[MemoryType.UserInteraction].append([])
                await self._set_current_action_memory(ActionMemoryType.Plan, message.event_content)
            case EventType.ActionExecution:
                await self._set_current_action_memory(ActionMemoryType.Action, message.event_content)
            case EventType.ScreenPerception:
                # 如果是初始化模式，屏幕感知应被设置为StartScreenPerception记忆
                if self.current_memory["init_mode"]:
                    await self._set_current_action_memory(ActionMemoryType.StartScreenPerception, message.event_content)
                else:
                    await self._set_current_action_memory(ActionMemoryType.EndScreenPerception, message.event_content)
            case EventType.Reflection:
                await self._set_current_action_memory(ActionMemoryType.ActionResult, message.event_content)

    async def _set_current_action_memory(self, memory_type, memory):
        self.current_memory[MemoryType.Actions][-1][memory_type] = memory
        await self.set_memory_ready(memory_type)

    # 当event为KeyInfoExtraction时，更新当前KeyInfo的记忆
    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.KeyInfoExtraction and message.status == EventStatus.DONE)
    async def update_key_info_memory(self, message: EventMessage, message_context):
        self.current_memory[MemoryType.KeyInfo].append(message.event_content)

    async def set_memory_ready(self, memory_type):
        if memory_type in self.current_memory_ready_event:
            # 通知等待记忆提供的任务
            self.current_memory_ready_event[memory_type].set()

    @listener(ListenerType.ON_CALLED, listen_filter=lambda message: message.call_type == CallType.Memory_GET)
    async def get_memory(self, message: CallMessage, message_context):
        memory_list = {}
        for memory_call_type in message.call_content:
            memory = None
            match memory_call_type:
                case MemoryCallType.GET_Instruction:
                    memory = await self._get_instruction_memory()
                case MemoryCallType.GET_Is_INIT_MODE:
                    memory = await self._get_is_init_mode()
                case MemoryCallType.GET_Current_Action_Memory:
                    memory = await self._get_current_action_memory(message.call_content[memory_call_type])
                case MemoryCallType.GET_Historical_Action_Memory:
                    memory = await self._get_historical_action_memory(message.call_content[memory_call_type])
                case MemoryCallType.GET_Key_Info:
                    memory = await self._get_key_info_memory()
                case MemoryCallType.GET_Current_User_Interaction:
                    memory = await self._get_current_user_interaction_memory()
            memory_list[memory_call_type] = memory
        return memory_list

    async def _get_instruction_memory(self):
        instruction_memory = self.current_memory.get(MemoryType.Instruction)
        return (instruction_memory["ori"] + (f" | Instructions added after user interaction: {','.join(instruction_memory['updated'])}" if len(
            instruction_memory["updated"]) > 0 else "")) if instruction_memory["ori"] is not None else None

    async def _get_is_init_mode(self):
        return self.current_memory["init_mode"]

    async def _get_current_action_memory(self, memory_request):
        # 检查要求的记忆是否已经就绪
        for memory_type in memory_request:
            if self.current_memory[MemoryType.Actions][-1][memory_type] is None:
                self.current_memory_ready_event[memory_type] = asyncio.Event()
                logger.debug(f"Waiting for memory {memory_type} to be ready...")
                await self.current_memory_ready_event[memory_type].wait()
                logger.debug(f"Memory {memory_type} is ready.")
                self.current_memory_ready_event.pop(memory_type)
        return self.current_memory[MemoryType.Actions][-1]

    async def _get_historical_action_memory(self, memory_request):
        # 无需检查记忆是否就绪
        memory = {}
        for memory_type in memory_request:
            memory_num = memory_request[memory_type] + 1
            historical_action_memories = self.current_memory[MemoryType.Actions][-memory_num:-1]
            memory[memory_type] = [historical_action_memory[memory_type] for historical_action_memory in historical_action_memories]
        return memory

    async def _get_key_info_memory(self):
        return self.current_memory[MemoryType.KeyInfo][-1] if len(self.current_memory[MemoryType.KeyInfo]) > 0 else []

    async def _get_current_user_interaction_memory(self):
        return self.current_memory[MemoryType.UserInteraction][-1]