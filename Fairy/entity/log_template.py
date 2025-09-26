from enum import Enum

from colorama import Style, Fore

from Citlali.core.agent import Agent
from Citlali.core.worker import Worker

class WorkerType(Enum):
    Agent = "Agent"
    Worker = "Worker"
    Tool = "Tool"

class LogEventType(Enum):
    WorkerStart = "Worker Start"
    WorkerCompleted = "Worker Completed"
    WorkerSkip = "Worker Skip"
    TaskComplete = "Task Complete"
    FunctionNotActive = "Function Not Active"
    MissingConfig = "Missing Config"
    Notice = "Notice"
    IntermediateResult = "Intermediate Results"

EventColor = {
    LogEventType.WorkerStart: Fore.GREEN,
    LogEventType.WorkerCompleted: Fore.GREEN,
    LogEventType.WorkerSkip: Fore.YELLOW,
    LogEventType.TaskComplete: Fore.GREEN,
    LogEventType.FunctionNotActive: Fore.YELLOW,
    LogEventType.MissingConfig: Fore.RED,
    LogEventType.Notice: Fore.BLUE,
    LogEventType.IntermediateResult: Fore.BLUE
}

class LogTemplate:
    def __init__(self, worker=None, worker_name=None):
        if isinstance(worker, Agent):
            self.worker_type = WorkerType.Agent
            self.worker_name = worker.name
        elif isinstance(worker, Worker):
            self.worker_type = WorkerType.Worker
            self.worker_name = worker.name
        else:
            self.worker_type = WorkerType.Tool
            self.worker_name = worker_name

    def label(self, log_type: LogEventType):
        target = f"{Fore.CYAN}[{self.worker_type.value}][{self.worker_name}]{Fore.RESET}"
        log_event = f"{EventColor[log_type]}{log_type.value}{Fore.RESET}"
        return f"{log_event} | {target} |"

    def log(self, log_type: LogEventType):
        match log_type:
            case LogEventType.WorkerStart:
                return lambda action: f"{self.label(LogEventType.WorkerStart)} {action} has started."
            case LogEventType.WorkerCompleted:
                return lambda action: f"{self.label(LogEventType.WorkerCompleted)} {action} has completed."
            case LogEventType.WorkerSkip:
                return lambda action, policy: f"{self.label(LogEventType.WorkerSkip)} {action} has been skipped, due to the policy: {policy}"
            case LogEventType.TaskComplete:
                return lambda: f"{self.label(LogEventType.TaskComplete)} Task has completed."
            case LogEventType.FunctionNotActive:
                return lambda feature, reason, related_config: f"{self.label(LogEventType.FunctionNotActive)} The feature {feature} is not active due to {reason}. {f'Configuration {related_config} can be set to enable the feature.' if related_config is not None else ''}"
            case LogEventType.MissingConfig:
                return lambda related_config, missing_config, status: f"{self.label(LogEventType.MissingConfig)} You have set {related_config} in the configuration, but have not configured {missing_config}, {'the process will terminate with an error' if status == 'critical' else 'so the configuration does not take effect'}."
            case LogEventType.Notice:
                return lambda message: f"{self.label(LogEventType.Notice)} {message}"
            case LogEventType.IntermediateResult:
                return lambda result_desc, result: f"{self.label(LogEventType.IntermediateResult)} {result_desc} : {result}"