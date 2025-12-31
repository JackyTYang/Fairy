"""
功能树构建器

负责构建和维护功能状态树
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

from .entities import (
    FeatureNode,
    FeatureTree,
    PageState,
    PathStep,
    PerceptionOutput
)
from .logger import get_logger

logger = get_logger("FeatureTreeBuilder")


class FeatureTreeBuilder:
    """功能树构建器

    负责构建和维护功能状态树

    Attributes:
        tree: 功能状态树
        current_path: 当前探索路径（PathStep列表）
        previous_state_id: 上一个状态ID
        feature_update_log: 功能更新日志
    """

    def __init__(self, root_feature_name: str, root_feature_description: str = ""):
        """初始化功能树

        Args:
            root_feature_name: 根功能名称
            root_feature_description: 根功能描述
        """
        # 创建根功能
        root_feature = FeatureNode(
            feature_id="root",
            feature_name=root_feature_name,
            feature_description=root_feature_description,
            parent_feature_id=None
        )

        # 初始化功能树
        self.tree = FeatureTree(
            root_feature_id="root",
            features={"root": root_feature}
        )

        # 当前探索路径
        self.current_path: List[PathStep] = []

        # 上一个状态ID（用于记录转换）
        self.previous_state_id: Optional[str] = None

        # 功能更新日志
        self.feature_update_log: List[Dict[str, Any]] = []

        logger.info(f"功能树初始化完成，根功能: {root_feature_name}")

    def initialize_from_plan(self, feature_structure: Dict[str, Any]):
        """从初始计划中提取功能结构

        Args:
            feature_structure: LLM输出的feature_structure字段
        """
        if not feature_structure:
            return

        sub_features = feature_structure.get('sub_features', [])

        for idx, sub_feat in enumerate(sub_features):
            feature_id = f"feature_{idx + 1}"
            feature_node = FeatureNode(
                feature_id=feature_id,
                feature_name=sub_feat['name'],
                feature_description=sub_feat.get('description', ''),
                parent_feature_id="root"
            )

            self.tree.features[feature_id] = feature_node
            self.tree.features["root"].sub_features.append(feature_id)

            logger.info(f"添加子功能: {sub_feat['name']}")

        # 记录初始化日志
        self.feature_update_log.append({
            'action': 'initialize',
            'features': [f['name'] for f in sub_features],
            'timestamp': datetime.now().isoformat()
        })

    def add_state(
        self,
        state_id: str,
        state_name: str,
        activity_name: str,
        perception_output: PerceptionOutput,
        feature_path: List[str],
        step_id: str,
        instruction: str,
        actions: List[Dict[str, Any]],
        success: bool
    ):
        """添加State到功能树

        Args:
            state_id: 状态ID
            state_name: 状态名称
            activity_name: Activity名称
            perception_output: 屏幕感知输出（包含双截图）
            feature_path: 当前功能路径，如 ["点餐功能", "选择套餐"]
            step_id: 步骤ID
            instruction: 指令
            actions: 动作列表
            success: 是否成功
        """
        # 检查是否已存在
        if state_id in self.tree.states:
            logger.debug(f"状态已存在: {state_id}")
            # 记录转换关系
            if self.previous_state_id:
                self._add_transition(self.previous_state_id, state_id, step_id)
            self.previous_state_id = state_id
            return

        # 创建PathStep
        from_state_id = self.previous_state_id if self.previous_state_id else "initial"
        from_state_name = self._get_state_name(from_state_id) if from_state_id != "initial" else "初始状态"

        path_step = PathStep(
            step_id=step_id,
            instruction=instruction,
            actions=actions,
            from_state_id=from_state_id,
            to_state_id=state_id,
            from_state_name=from_state_name,
            to_state_name=state_name,
            success=success,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        # 添加到当前路径
        self.current_path.append(path_step)

        # 创建PageState
        page_state = PageState(
            state_id=state_id,
            state_name=state_name,
            activity_name=activity_name,
            perception_output=perception_output,
            path_from_root=self.current_path.copy(),
            discovered_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        # 添加到树中
        self.tree.states[state_id] = page_state

        # 将State归属到功能节点
        feature_id = self._get_or_create_feature_by_path(feature_path)
        if feature_id and state_id not in self.tree.features[feature_id].states:
            self.tree.features[feature_id].states.append(state_id)

            # 如果是该功能的第一个状态，设置为入口状态
            if self.tree.features[feature_id].entry_state_id is None:
                self.tree.features[feature_id].entry_state_id = state_id

        # 记录转换关系
        if self.previous_state_id:
            self._add_transition(self.previous_state_id, state_id, step_id)

        self.previous_state_id = state_id

        logger.info(f"添加新状态: {state_id} -> 功能: {'/'.join(feature_path)}")

    def _add_transition(self, from_state_id: str, to_state_id: str, step_id: str):
        """添加状态转换"""
        self.tree.state_transitions.append((from_state_id, to_state_id, step_id))

        # 更新from_state的reachable_states
        if from_state_id in self.tree.states:
            from_state = self.tree.states[from_state_id]
            if to_state_id not in from_state.reachable_states:
                from_state.reachable_states.append(to_state_id)

    def _get_state_name(self, state_id: str) -> str:
        """获取状态名称"""
        if state_id in self.tree.states:
            return self.tree.states[state_id].state_name
        return state_id

    def _get_or_create_feature_by_path(self, feature_path: List[str]) -> Optional[str]:
        """根据功能路径获取或创建功能节点

        Args:
            feature_path: 功能路径，如 ["点餐功能", "选择套餐"]

        Returns:
            feature_id
        """
        if not feature_path or len(feature_path) == 0:
            return "root"

        # 如果只有根功能
        if len(feature_path) == 1:
            return "root"

        # 查找子功能（从第二个元素开始）
        target_feature_name = feature_path[-1]

        # 在所有子功能中查找
        for fid, feature in self.tree.features.items():
            if feature.feature_name == target_feature_name:
                return fid

        # 如果没找到，返回根功能（可能LLM还没创建这个子功能）
        logger.warning(f"未找到功能: {target_feature_name}，归属到根功能")
        return "root"

    def update_feature_structure(self, feature_update: Dict[str, Any], step_id: str):
        """根据LLM的feature_update更新功能树

        Args:
            feature_update: LLM输出的feature_update字段
            step_id: 触发更新的步骤ID
        """
        if not feature_update:
            return

        action = feature_update.get('action')

        if action == 'add_new':
            self._add_new_feature(feature_update.get('details', {}), step_id)

        elif action == 'rename':
            self._rename_feature(feature_update.get('details', {}), step_id)

        elif action == 'split':
            self._split_feature(feature_update.get('details', {}), step_id)

    def _add_new_feature(self, details: Dict[str, Any], step_id: str):
        """添加新发现的子功能"""
        new_feature_info = details.get('new_feature', {})
        if not new_feature_info:
            return

        parent_path = new_feature_info.get('parent_path', [])
        parent_id = self._get_or_create_feature_by_path(parent_path)

        # 创建新功能
        feature_id = f"feature_{len(self.tree.features)}"
        new_feature = FeatureNode(
            feature_id=feature_id,
            feature_name=new_feature_info['name'],
            feature_description=new_feature_info.get('description', ''),
            parent_feature_id=parent_id
        )

        # 添加到树中
        self.tree.features[feature_id] = new_feature
        self.tree.features[parent_id].sub_features.append(feature_id)

        # 记录日志
        self.feature_update_log.append({
            'step_id': step_id,
            'action': 'add_new',
            'feature_name': new_feature_info['name'],
            'reason': new_feature_info.get('reason', ''),
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"[{step_id}] 添加新功能: {new_feature_info['name']}")

    def _rename_feature(self, details: Dict[str, Any], step_id: str):
        """重命名功能"""
        old_name = details.get('rename_from', '')
        new_name = details.get('rename_to', '')
        reason = details.get('reason', '')

        # 查找功能
        for fid, feature in self.tree.features.items():
            if feature.feature_name == old_name:
                feature.feature_name = new_name

                self.feature_update_log.append({
                    'step_id': step_id,
                    'action': 'rename',
                    'from': old_name,
                    'to': new_name,
                    'reason': reason,
                    'timestamp': datetime.now().isoformat()
                })

                logger.info(f"[{step_id}] 功能重命名: {old_name} -> {new_name}")
                break

    def _split_feature(self, details: Dict[str, Any], step_id: str):
        """拆分功能（简化实现）"""
        original_name = details.get('split_feature', '')
        new_features = details.get('into', [])

        logger.info(f"[{step_id}] 功能拆分: {original_name} -> {[f['name'] for f in new_features]}")
        # 简化实现：仅记录日志，实际拆分逻辑较复杂
        self.feature_update_log.append({
            'step_id': step_id,
            'action': 'split',
            'original': original_name,
            'into': [f['name'] for f in new_features],
            'timestamp': datetime.now().isoformat()
        })

    def save_tree(self, filepath: Path):
        """保存功能树（同时保存完整版和压缩版）

        完整版：feature_tree.json - path_from_root包含完整step对象
        压缩版：feature_tree_compressed.json - path_from_root只包含step_id引用
        """
        # 保存完整版
        self.tree.save_to_file(filepath)
        logger.info(f"功能树（完整版）已保存: {filepath}")

        # ⭐ 保存压缩版
        compressed_path = filepath.parent / f"{filepath.stem}_compressed{filepath.suffix}"
        self.tree.save_to_file_compressed(compressed_path)

        # 计算压缩率
        import os
        original_size = os.path.getsize(filepath)
        compressed_size = os.path.getsize(compressed_path)
        compression_ratio = (1 - compressed_size / original_size) * 100

        logger.success(f"功能树（压缩版）已保存: {compressed_path}")
        logger.info(f"  - 原始大小: {original_size / 1024:.1f}KB")
        logger.info(f"  - 压缩后大小: {compressed_size / 1024:.1f}KB")
        logger.info(f"  - 压缩率: {compression_ratio:.1f}%")

    def save_update_log(self, filepath: Path):
        """保存功能更新日志"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.feature_update_log, f, indent=2, ensure_ascii=False)
        logger.info(f"功能更新日志已保存: {filepath}")

    def get_feature_summary(self) -> Dict[str, Any]:
        """获取功能树摘要"""
        return {
            'total_features': len(self.tree.features),
            'total_states': len(self.tree.states),
            'total_transitions': len(self.tree.state_transitions),
            'features': {fid: f.feature_name for fid, f in self.tree.features.items()}
        }

    def mark_feature_completed(self, feature_path: List[str], step_id: str):
        """标记功能为已完成

        当探索离开某个功能时调用，标记该功能已完成探索

        Args:
            feature_path: 要标记完成的功能路径
            step_id: 标记完成时的步骤ID
        """
        if not feature_path or len(feature_path) <= 1:
            return

        feature_name = feature_path[-1]

        # 查找对应的feature_id
        target_feature_id = None
        for fid, feature in self.tree.features.items():
            if feature.feature_name == feature_name:
                target_feature_id = fid
                break

        if not target_feature_id:
            logger.warning(f"未找到功能: {feature_name}，无法标记完成")
            return

        # 标记为completed
        feature_node = self.tree.features[target_feature_id]
        if feature_node.status != "completed":
            feature_node.status = "completed"
            feature_node.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            logger.info(f"✓ 功能已标记为完成: {feature_name} (feature_id={target_feature_id}, step={step_id})")
            logger.info(f"  - 该功能共探索了 {len(feature_node.states)} 个状态")

            # 记录到update log
            self.feature_update_log.append({
                'action': 'mark_completed',
                'feature_id': target_feature_id,
                'feature_name': feature_name,
                'step_id': step_id,
                'states_explored': len(feature_node.states),
                'timestamp': feature_node.completed_at
            })

