from enum import Enum


class EventType(Enum):
    GlobalPlan_CREATED = "GlobalPlan_CREATED"
    GlobalPlan_DONE = "GlobalPlan_DONE"
    Task_CREATED = "Task_CREATED"
    Plan_DONE = "Plan_DONE"
    ActionExecution_CREATED = "ActionExecution_CREATED"
    ActionExecution_DONE = "ActionExecution_DONE"
    ScreenPerception_DONE = "ScreenPerception_DONE"
    Reflection_DONE = "Reflection_DONE"
    KeyInfoExtraction_DONE = "KeyInfoExtraction_DONE"
    UserInteraction_DONE = "UserInteraction_DONE"
    UserChat_CREATED = "UserChat_CREATED"
    UserChat_DONE = "UserChat_DONE"
    Task_DONE = "Task_DONE"

class CallType(Enum):
    Memory_GET = 1
    Memory_SWITCH = 2
    App_Info_GET = 3
    Action_EXECUTE = 4