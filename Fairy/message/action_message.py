from datetime import datetime

from Fairy.tools.type import AtomicActionType


class ActionMessage:
    def __init__(self, action: AtomicActionType, status):
        self.action = action
        self.status = status
        self.timestamp = datetime.now().timestamp()

    def set_status(self, status):
        self.status = status
        self.timestamp = datetime.now().timestamp()