"""
Explorer 数据实体定义

定义Explorer的输入、输出、状态等所有数据结构
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import json


@dataclass
class ExplorationTarget:
    """探索目标 - Explorer的输入

    定义要探索的应用和功能

    Attributes:
        app_name: 应用名称，如 "麦当劳"
        app_package: 包名，如 "com.mcdonalds.app"
        app_description: 应用介绍，如 "提供点餐、外卖、优惠券等功能"
        feature_to_explore: 要探索的功能描述
        starting_state: 起始状态，默认"首页"
    """
    app_name: str
    app_package: str
    app_description: str
    feature_to_explore: str
    starting_state: str = "首页"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExplorationStep:
    """探索步骤

    代表探索计划中的一个步骤

    Attributes:
        step_id: 步骤ID，如 "step_1"
        instruction: 指令，传递给Executor的instruction
        sub_goal: 子目标，传递给Executor的current_sub_goal
        status: 状态 - pending/executing/completed/failed
        parent_step_id: 父步骤ID（用于构建树结构，预留）
        enable_reflection: 是否启用Executor的反思机制
        max_iterations: Executor的最大迭代次数
    """
    step_id: str
    instruction: str
    sub_goal: str
    status: str = "pending"  # pending/executing/completed/failed
    parent_step_id: Optional[str] = None
    enable_reflection: bool = True
    max_iterations: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExplorationPlan:
    """探索计划

    包含整体计划和步骤列表

    Attributes:
        plan_thought: LLM的计划思考过程
        overall_plan: 整体计划描述
        steps: 步骤列表
        completed_steps: 已完成的步骤ID列表
        pending_steps: 待执行的步骤ID列表
    """
    plan_thought: str
    overall_plan: str
    steps: List[ExplorationStep] = field(default_factory=list)
    completed_steps: List[str] = field(default_factory=list)
    pending_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plan_thought': self.plan_thought,
            'overall_plan': self.overall_plan,
            'steps': [step.to_dict() for step in self.steps],
            'completed_steps': self.completed_steps,
            'pending_steps': self.pending_steps
        }

    def save_to_file(self, filepath: Path):
        """保存计划到文件"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


@dataclass
class PerceptionOutput:
    """屏幕感知输出

    封装Perceptor的所有输出文件

    Attributes:
        screenshot_path: 原始截图路径（stable，5秒）
        marked_screenshot_path: 标记后截图路径（stable，5秒）
        xml_path: 原始XML路径（stable）
        compressed_xml_path: 压缩XML路径（stable）
        compressed_txt_path: 压缩TXT路径（stable）
        som_mapping_path: SoM映射JSON路径（stable）
        timestamp: 时间戳
        screen_size: 屏幕尺寸 (width, height)
        immediate_screenshot_path: 立刻截图路径（0.2秒，可选）
        immediate_marked_screenshot_path: 立刻截图标记后路径（0.2秒，可选）
        immediate_xml_path: 立刻截图XML路径（0.2秒，可选）
        immediate_compressed_xml_path: 立刻截图压缩XML路径（可选）
        immediate_compressed_txt_path: 立刻截图压缩文本路径（可选）
        immediate_som_mapping_path: 立刻截图SoM映射路径（可选）
    """
    screenshot_path: str
    marked_screenshot_path: str
    xml_path: str
    compressed_xml_path: str
    compressed_txt_path: str
    som_mapping_path: str
    timestamp: str
    screen_size: tuple
    immediate_screenshot_path: Optional[str] = None
    immediate_marked_screenshot_path: Optional[str] = None
    immediate_xml_path: Optional[str] = None
    immediate_compressed_xml_path: Optional[str] = None
    immediate_compressed_txt_path: Optional[str] = None
    immediate_som_mapping_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionSnapshot:
    """执行快照 - 记录每一步的完整状态

    Attributes:
        step_id: 步骤ID
        timestamp: 执行时间戳
        perception_output: 屏幕感知输出
        executor_result: Executor的执行结果（ExecutionOutput对象转为dict）
        navigation_path: 从首页到当前的导航路径
        step_output_dir: 该步骤的输出目录
    """
    step_id: str
    timestamp: str
    perception_output: PerceptionOutput
    executor_result: Dict[str, Any]  # ExecutionOutput.to_dict()
    navigation_path: List[str]
    step_output_dir: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_id': self.step_id,
            'timestamp': self.timestamp,
            'perception_output': self.perception_output.to_dict(),
            'executor_result': self.executor_result,
            'navigation_path': self.navigation_path,
            'step_output_dir': self.step_output_dir
        }

    def save_to_file(self, filepath: Path):
        """保存快照到文件"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


@dataclass
class ExplorationResult:
    """探索结果 - Explorer的输出

    Attributes:
        success: 是否成功完成探索
        target: 探索目标
        final_plan: 最终的探索计划
        execution_history: 执行历史（所有步骤的快照）
        total_steps: 总步骤数
        completed_steps: 完成步骤数
        failed_steps: 失败步骤数
        total_time: 总耗时（秒）
        output_dir: 输出目录
        error: 错误信息（如果失败）
    """
    success: bool
    target: ExplorationTarget
    final_plan: ExplorationPlan
    execution_history: List[ExecutionSnapshot]
    total_steps: int
    completed_steps: int
    failed_steps: int
    total_time: float
    output_dir: str
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'target': self.target.to_dict(),
            'final_plan': self.final_plan.to_dict() if self.final_plan else None,
            'execution_history': [snap.to_dict() for snap in self.execution_history],
            'total_steps': self.total_steps,
            'completed_steps': self.completed_steps,
            'failed_steps': self.failed_steps,
            'total_time': self.total_time,
            'output_dir': self.output_dir,
            'error': self.error
        }

    def save_to_file(self, filepath: Path):
        """保存结果到文件"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


@dataclass
class NavigationState:
    """导航状态（为后续状态树功能预留）

    Attributes:
        state_id: 状态ID
        page_name: 页面名称
        parent_state_id: 父状态ID
        children_state_ids: 子状态ID列表
    """
    state_id: str
    page_name: str
    parent_state_id: Optional[str] = None
    children_state_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
