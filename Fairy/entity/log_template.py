from enum import Enum

class WorkerType(Enum):
    Agent = "Agent"
    Tool = "Tool"


LogTemplate = {
    "worker_start": lambda worker_type, worker_name: f"[Worker Start] {worker_type} {worker_name} has started.",
    "worker_complete": lambda worker_type, worker_name: f"[Worker Shutdown - Completed] {worker_type} {worker_name} has completed.",
    "worker_skip": lambda worker_type, worker_name, policy: f"[Worker Skip] {worker_type} {worker_name} has been skipped, due to the policy: {policy}",
    "task_complete": lambda: f"[Task Completed] Task has completed.",
}