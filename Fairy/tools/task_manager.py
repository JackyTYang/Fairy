from loguru import logger

from Citlali.core.type import ListenerType
from Citlali.core.worker import listener, Worker
from Fairy.info_entity import UserInteractionInfo, GlobalPlanInfo, InstructionInfo
from Fairy.memory.short_time_memory_manager import MemoryType, ShortMemoryCallType
from Fairy.message_entity import EventMessage, CallMessage
from Fairy.tools.mobile_controller.action_type import AtomicActionType
from Fairy.type import EventType, EventStatus, CallType


class TaskManager(Worker):
    def __init__(self, runtime) -> None:
        super().__init__(runtime, "TaskManager")

        self.current_task = None
        self.finished_task_list = []


    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.GlobalPlan and message.status == EventStatus.DONE)
    async def on_task_create(self, message: EventMessage, message_context):
        global_plan_info: GlobalPlanInfo = message.event_content
        self.current_task = global_plan_info.current_sub_task
        await self.start_or_switch_app()
        await self.publish("app_channel", EventMessage(EventType.Task, EventStatus.CREATED,
            InstructionInfo(self.current_task['instruction'], global_plan_info.ins_language, self.current_task['key_info_request'])
        ))


    async def start_or_switch_app(self):
        await (await self.call(
            "ActionExecutor",
            CallMessage(CallType.Action_EXECUTE, {
                "atomic_action": AtomicActionType.StartApp,
                "args": {"app_package_name": self.current_task['app_package_name']},
            })
        ))

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda msg: msg.event == EventType.TaskFinish and msg.status == EventStatus.CREATED)
    async def on_task_finish(self, message: EventMessage, message_context):
        ...

    # @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
    #           listen_filter=lambda msg: msg.event == EventType.TaskFinish and msg.status == EventStatus.CREATED)
    # async def on_task_finish(self, message: EventMessage, message_context):
    #     last_task = self.task_list.pop()
    #     if len(self.task_list) == 0:
    #         logger.bind(log_tag="fairy_sys").critical("All tasks have been completed.")
    #     else:
    #         task_source = last_task["source"]
    #         match task_source:
    #             case "UserInteractorAgent":
    #                 # 子任务记忆出栈，调用pop_task_memory
    #                 previous_memory = await (await self.call(
    #                     "ShortTimeMemoryManager",
    #                     CallMessage(CallType.Memory_SWITCH)
    #                 ))
    #                 # 提取子任务的KeyInfo和Instruction
    #                 previous_key_info = previous_memory["memory"][MemoryType.KeyInfo]
    #                 previous_instruction = previous_memory["memory"][MemoryType.Instruction]
    #                 # 子任务的KeyInfo，合并父任务中
    #                 memory = await (await self.call(
    #                     "ShortTimeMemoryManager",
    #                     CallMessage(CallType.Memory_GET, {
    #                         ShortMemoryCallType.GET_Key_Info: None
    #                     })
    #                 ))
    #                 memory[ShortMemoryCallType.GET_Key_Info].extend(previous_key_info)
    #                 # 更新父任务的KeyInfo
    #                 await self.publish("app_channel", EventMessage(EventType.KeyInfoExtraction, EventStatus.DONE, memory[ShortMemoryCallType.GET_Key_Info]))
    #                 # 构建子任务响应，交回UserInteractorAgent
    #                 await self.publish("app_channel", EventMessage(EventType.TaskFinish, EventStatus.DONE, UserInteractionInfo("C", previous_instruction["thought"],  previous_instruction["ori"], previous_key_info)))
    #             case _:
    #                 logger.bind(log_tag="fairy_sys").error(f"Unknown task source: {task_source}")
    #                 return