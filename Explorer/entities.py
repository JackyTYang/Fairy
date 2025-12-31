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
        feature_structure: 功能结构（Initial Plan时输出）
        current_feature: 当前功能信息（每次Plan/Replan时输出）
        feature_update: 功能结构更新（Replan时可能输出）
    """
    plan_thought: str
    overall_plan: str
    steps: List[ExplorationStep] = field(default_factory=list)
    completed_steps: List[str] = field(default_factory=list)
    pending_steps: List[str] = field(default_factory=list)

    # 功能相关字段
    feature_structure: Dict[str, Any] = field(default_factory=dict)
    current_feature: Dict[str, Any] = field(default_factory=dict)
    feature_update: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plan_thought': self.plan_thought,
            'overall_plan': self.overall_plan,
            'steps': [step.to_dict() for step in self.steps],
            'completed_steps': self.completed_steps,
            'pending_steps': self.pending_steps,
            'feature_structure': self.feature_structure,
            'current_feature': self.current_feature,
            'feature_update': self.feature_update
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
class PathStep:
    """探索路径中的一个步骤

    记录从一个状态到另一个状态的转换

    Attributes:
        step_id: 步骤ID，如 "step_1"
        instruction: 执行的指令
        actions: 执行的动作列表
        from_state_id: 来源状态ID
        to_state_id: 目标状态ID
        from_state_name: 来源状态名称
        to_state_name: 目标状态名称
        success: 是否成功
        timestamp: 时间戳
    """
    step_id: str
    instruction: str
    actions: List[Dict[str, Any]]
    from_state_id: str
    to_state_id: str
    from_state_name: str
    to_state_name: str
    success: bool
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PageState:
    """页面状态（State = 页面，不是操作）

    代表应用的一个功能页面状态

    Attributes:
        state_id: 状态ID，格式 "state_<activity>_<hash>"
        state_name: 状态名称，如 "点餐界面"
        activity_name: Android Activity名称
        perception_output: 屏幕感知输出（包含双截图）
        path_from_root: 从首页到当前状态的完整步骤链路
        discovered_at: 首次发现的时间戳
        reachable_states: 从此状态可以到达的其他状态ID列表
    """
    state_id: str
    state_name: str
    activity_name: str
    perception_output: PerceptionOutput
    path_from_root: List[PathStep]
    discovered_at: str
    reachable_states: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'state_id': self.state_id,
            'state_name': self.state_name,
            'activity_name': self.activity_name,
            'perception_output': self.perception_output.to_dict(),
            'path_from_root': [step.to_dict() for step in self.path_from_root],
            'discovered_at': self.discovered_at,
            'reachable_states': self.reachable_states
        }

    def save_to_file(self, filepath: Path):
        """保存状态到文件"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


@dataclass
class FeatureNode:
    """功能节点

    代表应用的一个功能模块

    Attributes:
        feature_id: 功能ID
        feature_name: 功能名称，如 "点餐功能"
        feature_description: 功能描述
        parent_feature_id: 父功能ID（如果是子功能）
        states: 该功能包含的所有页面状态ID列表
        sub_features: 子功能ID列表
        entry_state_id: 该功能的入口状态ID
        status: 功能探索状态 - 'exploring' | 'completed'
        completed_at: 完成时间戳（如果已完成）
    """
    feature_id: str
    feature_name: str
    feature_description: str
    parent_feature_id: Optional[str] = None
    states: List[str] = field(default_factory=list)  # 存储state_id列表
    sub_features: List[str] = field(default_factory=list)  # 存储feature_id列表
    entry_state_id: Optional[str] = None
    status: str = "exploring"  # exploring | completed
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FeatureTree:
    """功能状态树

    管理整个探索过程中发现的功能和状态

    Attributes:
        root_feature_id: 根功能ID
        features: 功能ID到FeatureNode的映射
        states: 状态ID到PageState的映射
        steps: 步骤ID到PathStep的映射（去重存储）
        state_transitions: 状态转换记录 [(from_state_id, to_state_id, step_id)]
    """
    root_feature_id: str
    features: Dict[str, FeatureNode] = field(default_factory=dict)
    states: Dict[str, PageState] = field(default_factory=dict)
    steps: Dict[str, PathStep] = field(default_factory=dict)  # ⭐ 新增：集中存储所有steps
    state_transitions: List[tuple] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（完整版，包含所有step详情）"""
        return {
            'root_feature_id': self.root_feature_id,
            'features': {fid: f.to_dict() for fid, f in self.features.items()},
            'states': {sid: s.to_dict() for sid, s in self.states.items()},
            'steps': {step_id: step.to_dict() for step_id, step in self.steps.items()},  # ⭐ 集中存储
            'state_transitions': [
                {'from': f, 'to': t, 'step': s}
                for f, t, s in self.state_transitions
            ]
        }

    def to_dict_compressed(self) -> Dict[str, Any]:
        """序列化为压缩版字典（path_from_root只存step_id，需配合steps字典使用）"""
        # ⭐ 收集所有steps到steps字典（避免重复）
        all_steps = {}
        for state in self.states.values():
            for step in state.path_from_root:
                if step.step_id not in all_steps:
                    all_steps[step.step_id] = step

        # ⭐ states的path_from_root只存step_id列表
        compressed_states = {}
        for sid, state in self.states.items():
            # ⭐ 序列化perception_output，过滤掉null的immediate字段
            perception_dict = state.perception_output.to_dict()

            # 检查是否启用了immediate截图（通过判断immediate_screenshot_path是否为None）
            has_immediate = (perception_dict.get('immediate_screenshot_path') is not None)

            if not has_immediate:
                # 移除所有immediate相关字段
                immediate_fields = [
                    'immediate_screenshot_path',
                    'immediate_marked_screenshot_path',
                    'immediate_xml_path',
                    'immediate_compressed_xml_path',
                    'immediate_compressed_txt_path',
                    'immediate_som_mapping_path'
                ]
                for field in immediate_fields:
                    perception_dict.pop(field, None)

            state_dict = {
                'state_id': state.state_id,
                'state_name': state.state_name,
                'activity_name': state.activity_name,
                'perception_output': perception_dict,  # ⭐ 使用过滤后的字典
                'path_from_root': [step.step_id for step in state.path_from_root],  # ⭐ 只存ID
                'discovered_at': state.discovered_at,
                'reachable_states': state.reachable_states
            }
            compressed_states[sid] = state_dict

        return {
            'root_feature_id': self.root_feature_id,
            'features': {fid: f.to_dict() for fid, f in self.features.items()},
            'states': compressed_states,  # ⭐ 使用压缩版states
            'steps': {step_id: step.to_dict() for step_id, step in all_steps.items()},  # ⭐ 集中存储所有steps
            'state_transitions': [
                {'from': f, 'to': t, 'step': s}
                for f, t, s in self.state_transitions
            ]
        }

    def save_to_file(self, filepath: Path):
        """保存功能树到文件（完整版）"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def save_to_file_compressed(self, filepath: Path):
        """保存功能树到文件（压缩版）

        压缩版将path_from_root从完整step对象改为step_id引用，
        所有step对象集中存储在顶层steps字典中
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict_compressed(), f, indent=2, ensure_ascii=False)


@dataclass
class NavigationState:
    """导航状态（已废弃，使用PageState代替）

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
