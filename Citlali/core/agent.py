import functools

from .worker import Worker


class Agent(Worker):
    def __init__(self, runtime, name, desc=None):
        super().__init__(runtime, name ,desc)