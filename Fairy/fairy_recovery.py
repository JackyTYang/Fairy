import asyncio
import pickle
import time

from loguru import logger

from Citlali.core.type import ListenerType
from Citlali.core.worker import listener, Worker
from Fairy.config.fairy_config import FairyConfig
from Fairy.entity.type import EventChannel


class FairyRecovery(Worker):
    def __init__(self, runtime, config: FairyConfig):
        super().__init__(runtime, "FairyRecovery", "FairyRecovery")
        self.config = FairyConfig
        self.record_log = []
        self.restore_point_path = config.get_restore_point_path()

    async def start_record(self):
        while True:
            await self.update_restore_point()
            await asyncio.sleep(20)

    async def update_restore_point(self):
        current_time = time.strftime("%Y%m%d%H%M%S", time.localtime())
        with open(f"{self.restore_point_path}/system_restore.pkl", "wb") as f:
            pickle.dump((self.record_log, self.config), f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.bind(log_tag="fairy_sys").info(f"[RECOVERY Rec] Restore point updated at {current_time}.")

    def load_restore_point(self, restore_point_name):
        with open(restore_point_name, "rb") as f:
            self.record_log, self.config = pickle.load(f)

    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.GLOBAL_CHANNEL, listen_filter=lambda msg: True)
    async def event_recorder_for_global_channel(self, message, message_context):
        self.event_recorder(message, message_context)

    @listener(ListenerType.ON_NOTIFIED, channel=EventChannel.APP_CHANNEL, listen_filter=lambda msg: True)
    async def event_recorder_for_app_channel(self, message, message_context):
        self.event_recorder(message, message_context)

    def event_recorder(self, message, message_context):
        self.record_log.append({
            message: message,
            message_context: message_context
        })
