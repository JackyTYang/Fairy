"""
输出管理模块

统一管理执行器的所有输出：截图、标记图像、日志、执行结果等
"""

import json
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from Fairy.entity.info_entity import ScreenInfo


@dataclass
class ExecutionOutput:
    """执行输出结果

    包含执行的所有信息，方便传递给其他agent使用

    Attributes:
        success: 是否执行成功
        instruction: 执行的指令
        actions_taken: 执行的动作列表
        action_thought: LLM的动作思考
        action_expectation: 预期结果
        screen_before: 执行前的屏幕信息
        screen_after: 执行后的屏幕信息
        error: 错误信息（如果失败）
        execution_time: 执行时间（秒）
        timestamp: 执行时间戳
        output_files: 输出文件路径字典
    """
    success: bool
    instruction: str
    actions_taken: List[Dict]
    action_thought: str
    action_expectation: str
    execution_time: float
    timestamp: str
    output_files: Dict[str, str]
    screen_before: Optional[ScreenInfo] = None
    screen_after: Optional[ScreenInfo] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（不包含ScreenInfo对象）"""
        return {
            'success': self.success,
            'instruction': self.instruction,
            'actions_taken': self.actions_taken,
            'action_thought': self.action_thought,
            'action_expectation': self.action_expectation,
            'execution_time': self.execution_time,
            'timestamp': self.timestamp,
            'output_files': self.output_files,
            'error': self.error
        }

    def to_json(self, indent: int = 2) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save_to_file(self, filepath: Path) -> None:
        """保存结果到JSON文件"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())


class OutputManager:
    """输出管理器

    负责管理所有输出文件的保存和组织

    Examples:
        manager = OutputManager(output_dir=Path("output"))

        # 保存截图
        screenshot_path = manager.save_screenshot(screen_info, "before")

        # 保存标记图像
        marked_path = manager.save_marked_image(screen_info, mark_mapping)

        # 保存执行结果
        manager.save_execution_result(execution_output)
    """

    def __init__(self, output_dir: Path, session_id: Optional[str] = None):
        """
        Args:
            output_dir: 输出根目录
            session_id: 会话ID，用于区分不同的执行会话。如果不指定，使用时间戳
        """
        self.output_dir = Path(output_dir)
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")

        # 创建会话目录
        self.session_dir = self.output_dir / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        self.screenshots_dir = self.session_dir / "screenshots"
        self.marked_images_dir = self.session_dir / "marked_images"
        self.logs_dir = self.session_dir / "logs"
        self.results_dir = self.session_dir / "results"

        for dir_path in [self.screenshots_dir, self.marked_images_dir, self.logs_dir, self.results_dir]:
            dir_path.mkdir(exist_ok=True)

        # 执行计数器
        self.execution_count = 0

    def get_execution_id(self) -> str:
        """获取当前执行ID"""
        self.execution_count += 1
        return f"exec_{self.execution_count:03d}"

    def save_screenshot(self, screen_info: ScreenInfo, stage: str, execution_id: Optional[str] = None) -> Path:
        """保存截图

        Args:
            screen_info: 屏幕信息对象
            stage: 阶段标识，如 'before', 'after'
            execution_id: 执行ID，如果不指定则自动生成

        Returns:
            保存的文件路径
        """
        if execution_id is None:
            execution_id = self.get_execution_id()

        # 获取原始截图路径
        source_path = screen_info.screenshot_file_info.get_screenshot_fullpath()

        # 目标路径
        filename = f"{execution_id}_{stage}.jpg"
        target_path = self.screenshots_dir / filename

        # 复制文件
        shutil.copy(source_path, target_path)

        return target_path

    def save_marked_image(self, screen_info: ScreenInfo, stage: str, execution_id: Optional[str] = None) -> Optional[Path]:
        """保存标记后的图像

        Args:
            screen_info: 屏幕信息对象
            stage: 阶段标识
            execution_id: 执行ID

        Returns:
            保存的文件路径，如果没有标记则返回None
        """
        if not screen_info.perception_infos.use_set_of_marks_mapping:
            return None

        if execution_id is None:
            execution_id = self.get_execution_id()

        # 获取标记后的图像路径
        source_path = screen_info.screenshot_file_info.get_screenshot_fullpath()

        # 目标路径
        filename = f"{execution_id}_{stage}_marked.jpg"
        target_path = self.marked_images_dir / filename

        # 复制文件
        shutil.copy(source_path, target_path)

        return target_path

    def save_mark_mapping(self, screen_info: ScreenInfo, stage: str, execution_id: Optional[str] = None) -> Optional[Path]:
        """保存标记映射信息

        Args:
            screen_info: 屏幕信息对象
            stage: 阶段标识
            execution_id: 执行ID

        Returns:
            保存的文件路径
        """
        if not screen_info.perception_infos.use_set_of_marks_mapping:
            return None

        if execution_id is None:
            execution_id = self.get_execution_id()

        # 构建标记映射数据
        mapping_data = {
            'execution_id': execution_id,
            'stage': stage,
            'timestamp': datetime.now().isoformat(),
            'mark_mapping': {
                str(mark_num): coords
                for mark_num, coords in screen_info.perception_infos.SoM_mapping.items()
            }
        }

        # 保存为JSON
        filename = f"{execution_id}_{stage}_mapping.json"
        filepath = self.marked_images_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, indent=2, ensure_ascii=False)

        return filepath

    def save_execution_result(self, result: ExecutionOutput) -> Path:
        """保存执行结果

        Args:
            result: 执行输出对象

        Returns:
            保存的文件路径
        """
        filename = f"result_{result.timestamp.replace(':', '-').replace(' ', '_')}.json"
        filepath = self.results_dir / filename

        result.save_to_file(filepath)

        return filepath

    def get_session_summary(self) -> Dict[str, Any]:
        """获取会话摘要

        Returns:
            包含会话统计信息的字典
        """
        return {
            'session_id': self.session_id,
            'session_dir': str(self.session_dir),
            'execution_count': self.execution_count,
            'screenshots_count': len(list(self.screenshots_dir.glob('*.jpg'))),
            'marked_images_count': len(list(self.marked_images_dir.glob('*_marked.jpg'))),
            'results_count': len(list(self.results_dir.glob('*.json')))
        }

    def save_session_summary(self) -> Path:
        """保存会话摘要"""
        summary = self.get_session_summary()
        filepath = self.session_dir / "session_summary.json"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        return filepath
