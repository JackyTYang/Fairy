from loguru import logger

from Citlali.core.type import ListenerType
from Citlali.core.worker import listener, Worker
from Fairy.entity.info_entity import GlobalPlanInfo, InstructionInfo
from Fairy.entity.log_template import LogTemplate, LogEventType
from Fairy.entity.message_entity import EventMessage, CallMessage
from Fairy.tools.mobile_controller.action_type import AtomicActionType
from Fairy.entity.type import EventType, CallType, EventChannel, EventStatus


class TaskManager(Worker):
    def __init__(self, runtime) -> None:
        super().__init__(runtime, "TaskManager")
        self.log_t = LogTemplate(self)  # 日志模板

        self.current_task = None
        self.finished_task_list = []


    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.GLOBAL_CHANNEL,
              listen_filter=lambda msg: msg.match(EventType.Plan, EventStatus.DONE))
    async def on_task_create(self, message: EventMessage, message_context):
        # GLOBAL_CHANNEL发布Task CREATE事件 & 记录日志
        await self.publish(EventChannel.GLOBAL_CHANNEL, EventMessage(EventType.Task, EventStatus.CREATED))
        logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerStart)("Task Execution"))

        global_plan_info: GlobalPlanInfo = message.event_content
        self.current_task = global_plan_info.current_sub_task
        await self.start_or_switch_app()

        instruction_info = InstructionInfo(
            self.current_task['instruction'],
            global_plan_info.ins_language,
            self.current_task['app_package_name'],
            self.current_task['key_info_request']
        )

        # APP_CHANNEL发布Task CREATE事件
        await self.publish(EventChannel.APP_CHANNEL, EventMessage(EventType.Task, EventStatus.CREATED, instruction_info))


    async def start_or_switch_app(self):
        await (await self.call(
            "ActionExecutor",
            CallMessage(CallType.Action_EXECUTE, {
                "atomic_action": AtomicActionType.StartApp,
                "args": {"app_package_name": self.current_task['app_package_name']},
            })
        ))

    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.APP_CHANNEL,
              listen_filter=lambda msg: msg.match(EventType.Task, EventStatus.DONE))
    async def on_task_finish(self, message: EventMessage, message_context):
        # GLOBAL_CHANNEL发布Task DONE事件 & 记录日志
        await self.publish(EventChannel.GLOBAL_CHANNEL, EventMessage(EventType.Task, EventStatus.DONE, message))
        logger.bind(log_tag="fairy_sys").info(self.log_t.log(LogEventType.WorkerCompleted)("Task Execution"))

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