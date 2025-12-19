"""
设备管理单例

确保全局只有一个 uiautomator2 连接
"""
import uiautomator2 as u2
from typing import Optional


class DeviceManager:
    """UIAutomator2 设备连接单例管理器"""

    _instance: Optional['DeviceManager'] = None
    _device = None
    _device_id: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_device(cls, device_id: Optional[str] = None):
        """
        获取设备连接（单例）

        Args:
            device_id: 设备ID，如果为None则自动连接

        Returns:
            uiautomator2.Device 实例
        """
        instance = cls()

        # 如果已经连接了相同设备，直接返回
        if instance._device is not None and instance._device_id == device_id:
            return instance._device

        # 如果设备ID不同，重新连接
        if device_id is None or device_id == "":
            instance._device = u2.connect()
            instance._device_id = None
        else:
            instance._device = u2.connect(device_id)
            instance._device_id = device_id

        return instance._device

    @classmethod
    def reset(cls):
        """重置单例（用于测试）"""
        instance = cls()
        instance._device = None
        instance._device_id = None
