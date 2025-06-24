from enum import Enum

class WorkerType(Enum):
    Agent = "Agent"
    Tool = "Tool"


LogTemplate = {
    "worker_start": lambda worker_type, worker_name: f"[Worker Start] {worker_type} {worker_name} has started.",
    "worker_complete": lambda worker_type, worker_name: f"[Worker Shutdown - Completed] {worker_type} {worker_name} has completed.",
    "worker_skip": lambda worker_type, worker_name, policy: f"[Worker Skip] {worker_type} {worker_name} has been skipped, due to the policy: {policy}",
    "task_complete": lambda: f"[Task Completed] Task has completed.",
    "function_not_active": lambda worker_type, worker_name, feature, reason, related_config: f"[Function Not Active] {worker_type} {worker_name}: The feature {feature} is not active due to {reason}. {f'Configuration {related_config} can be set to enable the feature.' if related_config is not None else ''}",
    "missing_config": lambda worker_type, worker_name, related_config, missing_config, status : f"[Missing Config] {worker_type} {worker_name}: You have set {related_config} in the configuration, but have not configured {missing_config}, {'the process will terminate with an error' if status=='critical' else 'so the configuration does not take effect'}."
}