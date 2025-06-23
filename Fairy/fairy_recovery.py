from Citlali.core.type import ListenerType
from Citlali.core.worker import listener, Worker


class FairyRecovery(Worker):
    def __init__(self, runtime):
        super().__init__(runtime, "FairyRecovery", "FairyRecovery")
        self.record_log = {}

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel")
    def event_recorder(self, message, message_context):
        self.record_log[message.event].append(message)