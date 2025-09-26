import asyncio
import time
from enum import Enum
from Citlali.core.type import ListenerType
from Citlali.core.worker import Worker, listener
from Fairy.config.fairy_config import FairyConfig
from Fairy.entity.info_entity import ActionInfo, ProgressInfo
from Fairy.entity.log_template import LogTemplate
from Fairy.entity.message_entity import EventMessage, CallMessage
from Fairy.tools.mobile_controller.action_type import AtomicActionType
from Fairy.entity.type import EventType, CallType, EventChannel, EventStatus
from loguru import logger
import pickle

class MemoryType(Enum):
    GlobalInstruction = 0
    GlobalPlan = 1
    Instruction = 2
    Actions = 3
    UserInteraction = 4
    KeyInfo = 5


class ActionMemoryType(Enum):
    StartScreenPerception = 1
    Plan = 2
    Action = 3
    ActionResult = 4
    EndScreenPerception = 5

class ShortMemoryCallType(Enum):
    GET_Instruction = 1
    GET_Current_Action_Memory = 2
    GET_Historical_Action_Memory = 3
    GET_Is_INIT_MODE = 4
    GET_Key_Info = 5
    GET_Current_User_Interaction = 6
    GET_Global_Plan_Info = 7
    GET_Global_Instruction = 8

class ShortTimeMemoryManager(Worker):
    def __init__(self, runtime, config:FairyConfig):
        super().__init__(runtime, "ShortTimeMemoryManager", "ShortTimeMemoryManager")
        self.log_t = LogTemplate(self)  # 日志模板

        self.memory_list = []
        # self.old_memory_list = []

        self.task_name = None
        self.current_memory = None
        self.current_memory_ready_event = None
        self.global_memory = {
            MemoryType.GlobalInstruction: None,
            MemoryType.GlobalPlan: [],
        }

        self.stm_restore_point_path = config.get_restore_point_path()

    def build_restore_point(self):
        current_time = time.strftime("%Y%m%d%H%M%S", time.localtime())
        with open(f"{self.stm_restore_point_path}/short_time_memory_backup_{current_time}.pkl", "wb") as f:
            short_time_memory = (
                    self.memory_list,
                    self.task_name,
                    self.current_memory,
                    self.current_memory_ready_event,
                    self.global_memory
                )
            # noinspection PyTypeChecker
            pickle.dump(short_time_memory, f, protocol=pickle.HIGHEST_PROTOCOL)

    def load_restore_point(self, restore_point_name):
        with open(restore_point_name, "rb") as f:
            short_time_memory = pickle.load(f)
        self.memory_list, self.task_name, self.current_memory, self.current_memory_ready_event, self.global_memory = short_time_memory

    def new_memory(self, task_name=None):
        self.task_name = task_name
        self.current_memory = {
            MemoryType.Instruction: None,
            MemoryType.Actions: [],
            MemoryType.KeyInfo:[],
            MemoryType.UserInteraction: [],
            "init_mode": False
        }
        self.current_memory_ready_event = {}

    def push_task_memory(self, task_name):
        self.build_restore_point()  # 建立恢复点
        self.memory_list.append({
            "task_name": self.task_name,
            "memory": self.current_memory,
            "memory_ready_event": self.current_memory_ready_event,
            "global_plan_memory": self.global_memory[MemoryType.GlobalPlan][-1],
        }) # 保存当前短时记忆
        # 新建一个短时记忆
        self.new_memory(task_name)

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

    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.APP_CHANNEL,
              listen_filter=lambda msg: msg.match(EventType.Task, EventStatus.CREATED))
    async def create_task_memory(self, message: EventMessage, message_context):
        memory_name = f"Task {len(self.memory_list)+1}"
        if len(self.memory_list) == 0 and self.current_memory is None:
            self.new_memory(memory_name) # 初始化短时记忆(Main Task)
        else:
            # self.push_task_memory("Sub-Task:"+ message.event_content.get("task_name", "no_named_task")) # 保存当前短时记忆
            self.push_task_memory(memory_name) # 保存当前短时记忆

        # 设为初始化模式
        self.current_memory["init_mode"] = True
        # 新增一个Action
        self.add_action()
        # 设置最初的用户指示
        self.current_memory[MemoryType.Instruction] = message.event_content
        # self.current_memory[MemoryType.Instruction]["thought"] = message.event_content.get("thought", None)
        await self.set_memory_ready(MemoryType.Instruction)

    # 当event为UserInteraction时，更新当前Instruction的记忆
    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.APP_CHANNEL,
              listen_filter=lambda msg: msg.match(EventType.UserInteraction, EventStatus.DONE))
    async def update_instruction_memory(self, message: EventMessage, message_context):
        if message.event_content.interaction_status == "A":
            self.current_memory[MemoryType.Instruction].updated.append(message.event_content.response)
            # 构建本次的Action
            self.current_memory[MemoryType.Actions][-1][ActionMemoryType.Action] = ActionInfo(
                "User Instruction", [{"name": AtomicActionType.UserInstruction}], "Get User Responses.", ""
            )
            self.current_memory[MemoryType.Actions][-1][ActionMemoryType.ActionResult] = ProgressInfo(
                "A", None, None
            )
            # 用户询问轮，屏幕信息不发生变化
            self.current_memory[MemoryType.Actions][-1][ActionMemoryType.EndScreenPerception] = self.current_memory[MemoryType.Actions][-1][ActionMemoryType.StartScreenPerception]
        else:
            pass # 其他情况无需更新记忆

    # 当event为UserChat时，更新当前UserInteraction的记忆
    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.APP_CHANNEL,
              listen_filter=lambda msg: msg.match(EventType.UserChat, EventStatus.DONE))
    async def update_current_user_interaction_memory(self, message: EventMessage, message_context):
        self.current_memory[MemoryType.UserInteraction][-1].append(message.event_content)

    # 当event为Plan、ActionDecision、ScreenPerception、Reflection时，更新当前Action的记忆
    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.APP_CHANNEL,
              listen_filter=lambda msg: msg.match_list([EventType.Plan, EventType.ActionDecision, EventType.Reflection, EventType.ScreenPerception], EventStatus.DONE))
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
            case EventType.ActionDecision:
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
    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.APP_CHANNEL,
              listen_filter=lambda msg: msg.match(EventType.KeyInfoExtraction, EventStatus.DONE))
    async def update_key_info_memory(self, message: EventMessage, message_context):
        self.current_memory[MemoryType.KeyInfo].append(message.event_content)

    async def set_memory_ready(self, memory_type):
        if memory_type in self.current_memory_ready_event:
            # 通知等待记忆提供的任务
            self.current_memory_ready_event[memory_type].set()

    # 当event为GlobalPlan时，更新当前GlobalPlan的记忆
    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.GLOBAL_CHANNEL,
              listen_filter=lambda msg: msg.match(EventType.Plan, EventStatus.DONE))
    async def update_global_plan_memory(self, message: EventMessage, message_context):
        self.global_memory[MemoryType.GlobalPlan].append(message.event_content)

    # 当event为INIT时，更新当前GlobalInstruction的记忆
    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.GLOBAL_CHANNEL,
              listen_filter=lambda msg: msg.match(EventType.INIT, EventStatus.CREATED))
    async def set_global_instruction_memory(self, message: EventMessage, message_context):
        self.global_memory[MemoryType.GlobalInstruction] = message.event_content["user_instruction"]

    @listener(ListenerType.ON_CALLED, listen_filter=lambda message: message.call_type == CallType.Memory_GET)
    async def get_memory(self, message: CallMessage, message_context):
        memory_list = {}
        for memory_call_type in message.call_content:
            memory = None
            match memory_call_type:
                case ShortMemoryCallType.GET_Instruction:
                    memory = self.current_memory.get(MemoryType.Instruction)
                case ShortMemoryCallType.GET_Is_INIT_MODE:
                    memory = self.current_memory.get("init_mode")
                case ShortMemoryCallType.GET_Current_Action_Memory:
                    memory = await self._get_current_action_memory(message.call_content[memory_call_type])
                case ShortMemoryCallType.GET_Historical_Action_Memory:
                    memory = await self._get_historical_action_memory(message.call_content[memory_call_type])
                case ShortMemoryCallType.GET_Key_Info:
                    memory = self.current_memory.get(MemoryType.KeyInfo)[-1] if len(self.current_memory.get(MemoryType.KeyInfo)) > 0 else []
                case ShortMemoryCallType.GET_Current_User_Interaction:
                    memory = self.current_memory.get(MemoryType.UserInteraction)[-1]
                case ShortMemoryCallType.GET_Global_Plan_Info:
                    memory = self.global_memory[MemoryType.GlobalPlan][-1]
                case ShortMemoryCallType.GET_Global_Instruction:
                    memory = self.global_memory[MemoryType.GlobalInstruction]
            memory_list[memory_call_type] = memory
        return memory_list

    async def _get_current_action_memory(self, memory_request):
        # 检查要求的记忆是否已经就绪
        memory = {}
        for memory_type in memory_request:
            if self.current_memory[MemoryType.Actions][-1][memory_type] is None:
                self.current_memory_ready_event[memory_type] = asyncio.Event()
                logger.bind(log_tag="fairy_sys").debug(f"Waiting for memory {memory_type} to be ready...")
                await self.current_memory_ready_event[memory_type].wait()
                logger.bind(log_tag="fairy_sys").debug(f"Memory {memory_type} is ready.")
                self.current_memory_ready_event.pop(memory_type)
            memory[memory_type] = self.current_memory[MemoryType.Actions][-1][memory_type]
        return memory

    async def _get_historical_action_memory(self, memory_request):
        # 无需检查记忆是否就绪
        memory = {}
        for memory_type in memory_request:
            if memory_request[memory_type] == float("INF"):
                historical_action_memories = self.current_memory[MemoryType.Actions]
            else:
                memory_num = memory_request[memory_type] + 1
                historical_action_memories = self.current_memory[MemoryType.Actions][-memory_num:-1]
            memory[memory_type] = [historical_action_memory[memory_type] for historical_action_memory in historical_action_memories]
        return memory