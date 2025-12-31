"""
State识别器

负责识别页面状态，生成state_id
"""

import hashlib
import json
from typing import Optional
from .logger import get_logger

logger = get_logger("StateIdentifier")


class StateIdentifier:
    """State识别器

    根据Activity和UI结构识别页面状态

    Attributes:
        state_cache: 已识别的state_id缓存
    """

    def __init__(self):
        self.state_cache = {}  # {state_id: ui_hash}
        logger.info("StateIdentifier初始化完成")

    def identify_state(self, screen_info, perception_output) -> str:
        """识别State，返回state_id

        Args:
            screen_info: Executor返回的ScreenInfo对象
            perception_output: PerceptionOutput对象

        Returns:
            state_id: 格式为 "state_<activity>_<hash>"
        """
        # 获取Activity名称
        activity = screen_info.current_activity_info.activity
        activity_short = self._shorten_activity(activity)

        # 生成UI结构哈希
        ui_hash = self._hash_ui_structure(perception_output)

        # 生成state_id
        state_id = f"state_{activity_short}_{ui_hash}"

        # 检查是否是新状态
        if state_id not in self.state_cache:
            self.state_cache[state_id] = ui_hash
            logger.info(f"发现新状态: {state_id}")
        else:
            logger.debug(f"状态已存在: {state_id}")

        return state_id

    def _shorten_activity(self, activity: str) -> str:
        """缩短Activity名称

        Args:
            activity: 完整的Activity名称

        Returns:
            简化的名称
        """
        # 提取最后一个.后的部分
        if '.' in activity:
            parts = activity.split('.')
            # 取最后一个部分，移除"Activity"后缀
            short_name = parts[-1].replace('Activity', '').replace('activity', '')
            return short_name.lower()
        return activity.lower()

    def _hash_ui_structure(self, perception_output) -> str:
        """基于UI结构生成哈希

        使用压缩后的XML来生成哈希，过滤动态内容

        Args:
            perception_output: PerceptionOutput对象

        Returns:
            8位哈希值
        """
        try:
            # 读取压缩后的文本描述（已经过滤了大部分动态内容）
            with open(perception_output.compressed_txt_path, 'r', encoding='utf-8') as f:
                ui_text = f.read()

            # 进一步过滤：移除数字（可能是动态的计数、时间等）
            # 保留结构和文本标签
            filtered_text = self._filter_dynamic_content(ui_text)

            # 计算哈希
            hash_obj = hashlib.md5(filtered_text.encode('utf-8'))
            return hash_obj.hexdigest()[:8]

        except Exception as e:
            logger.warning(f"UI哈希生成失败: {e}")
            # 兜底：使用时间戳
            import time
            return hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

    def _filter_dynamic_content(self, ui_text: str) -> str:
        """过滤动态内容

        移除可能变化的内容（数字、时间等），保留结构

        Args:
            ui_text: UI文本描述

        Returns:
            过滤后的文本
        """
        import re

        # 移除纯数字（保留包含文字的）
        filtered = re.sub(r'\b\d+\b', '', ui_text)

        # 移除常见的动态模式
        # 时间格式：HH:MM, YYYY-MM-DD等
        filtered = re.sub(r'\d{1,2}:\d{2}', '', filtered)
        filtered = re.sub(r'\d{4}-\d{2}-\d{2}', '', filtered)

        # 移除多余空白
        filtered = re.sub(r'\s+', ' ', filtered)

        return filtered.strip()

    def get_state_name(self, screen_info, state_id: str) -> str:
        """生成State名称（辅助方法）

        基于Activity和state_id生成可读的名称

        Args:
            screen_info: ScreenInfo对象
            state_id: 状态ID

        Returns:
            状态名称
        """
        activity = screen_info.current_activity_info.activity
        activity_short = self._shorten_activity(activity)

        # 简单的名称生成（后续可以让LLM来命名）
        return f"{activity_short}_page"
