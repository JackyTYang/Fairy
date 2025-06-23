from datetime import datetime
from typing import List

from Fairy.entity.type import EventType, EventStatus


class EventMessage:
    def __init__(self, event: EventType, status:EventStatus, event_content=None):
        self.event = event
        self.status = status
        self.event_content = event_content
        self.timestamp = datetime.now().timestamp()

    def __str__(self):
        return f"EventMessage: {self.event}, {self.status}, {self.event_content}"

    def match(self, event: EventType, status: EventStatus):
        return self.event == event and self.status == status

    def match_list(self, event: List[EventType], status: EventStatus):
        return self.event in event and self.status == status

class CallMessage:
    def __init__(self, call_type, call_content=None):
        self.call_type = call_type
        self.call_content = call_content