from datetime import datetime

from Fairy.type import EventType


class EventMessage:
    def __init__(self, event: EventType, event_content=None):
        self.event = event
        self.event_content = event_content
        self.timestamp = datetime.now().timestamp()

    def __str__(self):
        return f"EventMessage: {self.event}, {self.event_content}"

class CallMessage:
    def __init__(self, call_type, call_content=None):
        self.call_type = call_type
        self.call_content = call_content