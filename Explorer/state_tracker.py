"""
状态跟踪器

负责记录执行路径、保存状态快照、维护导航历史
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from .entities import (
    ExplorationStep,
    ExecutionSnapshot,
    PerceptionOutput,
    NavigationState
)
from .logger import get_logger

logger = get_logger("StateTracker")


class StateTracker:
    """状态跟踪器

    管理探索过程中的状态记录

    Attributes:
        output_dir: 输出根目录
        execution_history: 执行历史列表
        navigation_path: 导航路径（页面名称列表）
        step_counter: 步骤计数器
    """

    def __init__(self, output_dir: Path):
        """
        Args:
            output_dir: 输出根目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.execution_history: List[ExecutionSnapshot] = []
        self.navigation_path: List[str] = ["首页"]
        self.step_counter = 0

        # ⭐ 新增：记录实际执行的计划步骤
        self.executed_plan_steps = []

        logger.info(f"StateTracker初始化，输出目录: {self.output_dir}")

    def create_step_output_dir(self, step_id: str) -> Path:
        """为步骤创建输出目录

        Args:
            step_id: 步骤ID

        Returns:
            步骤输出目录路径
        """
        step_dir = self.output_dir / step_id
        step_dir.mkdir(exist_ok=True)
        return step_dir

    async def record_step(
        self,
        step: ExplorationStep,
        perception_output: PerceptionOutput,
        executor_result: dict
    ) -> ExecutionSnapshot:
        """记录一步的执行状态

        将Perceptor输出的所有文件复制到步骤目录（包括双截图），并保存执行结果

        Args:
            step: 执行的步骤
            perception_output: Perceptor输出（包含双截图信息）
            executor_result: Executor执行结果（ExecutionOutput.to_dict()）

        Returns:
            ExecutionSnapshot: 执行快照
        """
        self.step_counter += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"记录步骤: {step.step_id}")

        # 1. 创建步骤输出目录结构
        step_dir = self.create_step_output_dir(step.step_id)

        # ⭐ 创建 immediate 和 stable 子目录
        immediate_dir = step_dir / "immediate"
        stable_dir = step_dir / "stable"
        immediate_dir.mkdir(exist_ok=True)
        stable_dir.mkdir(exist_ok=True)

        # 2. 复制稳定截图（5秒）到 stable/ 目录
        stable_files = {
            'screenshot': perception_output.screenshot_path,
            'marked_screenshot': perception_output.marked_screenshot_path,
            'xml': perception_output.xml_path,
            'compressed_xml': perception_output.compressed_xml_path,
            'compressed_txt': perception_output.compressed_txt_path,
            'som_mapping': perception_output.som_mapping_path
        }

        for file_type, src_path in stable_files.items():
            if src_path and Path(src_path).exists():
                dst_path = stable_dir / Path(src_path).name
                shutil.copy2(src_path, dst_path)
                logger.debug(f"复制稳定截图文件: stable/{Path(src_path).name}")

        # ⭐ 3. 复制立刻截图（0.2秒）到 immediate/ 目录（完整文件）
        has_immediate = False
        if perception_output.immediate_screenshot_path:
            immediate_files = {
                'immediate_screenshot': perception_output.immediate_screenshot_path,
                'immediate_marked_screenshot': perception_output.immediate_marked_screenshot_path,
                'immediate_xml': perception_output.immediate_xml_path,
                'immediate_compressed_xml': perception_output.immediate_compressed_xml_path,
                'immediate_compressed_txt': perception_output.immediate_compressed_txt_path,
                'immediate_som_mapping': perception_output.immediate_som_mapping_path
            }

            for file_type, src_path in immediate_files.items():
                if src_path and Path(src_path).exists():
                    dst_path = immediate_dir / Path(src_path).name
                    shutil.copy2(src_path, dst_path)
                    logger.debug(f"复制立刻截图文件: immediate/{Path(src_path).name}")
                    has_immediate = True

            if has_immediate:
                logger.info(f"✓ 双截图已保存: immediate/ 和 stable/（包含完整的SoM标记文件）")

        # 4. 构建更新后的 PerceptionOutput（指向新位置）
        # stable文件路径
        copied_perception = PerceptionOutput(
            screenshot_path=str(stable_dir / Path(perception_output.screenshot_path).name),
            marked_screenshot_path=str(stable_dir / Path(perception_output.marked_screenshot_path).name),
            xml_path=str(stable_dir / Path(perception_output.xml_path).name),
            compressed_xml_path=str(stable_dir / Path(perception_output.compressed_xml_path).name),
            compressed_txt_path=str(stable_dir / Path(perception_output.compressed_txt_path).name),
            som_mapping_path=str(stable_dir / Path(perception_output.som_mapping_path).name),
            timestamp=perception_output.timestamp,
            screen_size=perception_output.screen_size,
            # immediate文件路径
            immediate_screenshot_path=str(immediate_dir / Path(perception_output.immediate_screenshot_path).name) if perception_output.immediate_screenshot_path else None,
            immediate_marked_screenshot_path=str(immediate_dir / Path(perception_output.immediate_marked_screenshot_path).name) if perception_output.immediate_marked_screenshot_path else None,
            immediate_xml_path=str(immediate_dir / Path(perception_output.immediate_xml_path).name) if perception_output.immediate_xml_path else None,
            immediate_compressed_xml_path=str(immediate_dir / Path(perception_output.immediate_compressed_xml_path).name) if perception_output.immediate_compressed_xml_path else None,
            immediate_compressed_txt_path=str(immediate_dir / Path(perception_output.immediate_compressed_txt_path).name) if perception_output.immediate_compressed_txt_path else None,
            immediate_som_mapping_path=str(immediate_dir / Path(perception_output.immediate_som_mapping_path).name) if perception_output.immediate_som_mapping_path else None
        )

        # 5. 保存Executor结果
        executor_result_path = step_dir / "executor_result.json"
        with open(executor_result_path, 'w', encoding='utf-8') as f:
            json.dump(executor_result, f, indent=2, ensure_ascii=False)

        # 6. 创建执行快照
        snapshot = ExecutionSnapshot(
            step_id=step.step_id,
            timestamp=timestamp,
            perception_output=copied_perception,
            executor_result=executor_result,
            navigation_path=self.navigation_path.copy(),
            step_output_dir=str(step_dir)
        )

        # 7. 保存快照到文件
        snapshot.save_to_file(step_dir / "snapshot.json")

        # 8. 添加到历史记录
        self.execution_history.append(snapshot)

        logger.success(f"步骤 {step.step_id} 状态已记录")

        return snapshot

    def update_navigation_path(self, new_page: str):
        """更新导航路径

        Args:
            new_page: 新页面名称
        """
        self.navigation_path.append(new_page)
        logger.debug(f"导航路径更新: {' -> '.join(self.navigation_path)}")

    def save_navigation_path(self):
        """保存导航路径到文件"""
        navigation_path_file = self.output_dir / "navigation_path.json"
        with open(navigation_path_file, 'w', encoding='utf-8') as f:
            json.dump({
                'path': self.navigation_path,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)
        logger.debug(f"导航路径已保存: {navigation_path_file}")

    def get_current_path(self) -> List[str]:
        """获取当前导航路径

        Returns:
            导航路径列表
        """
        return self.navigation_path.copy()

    def get_execution_history(self) -> List[ExecutionSnapshot]:
        """获取执行历史

        Returns:
            执行历史列表
        """
        return self.execution_history.copy()

    def save_state_tree(self):
        """保存状态树（预留接口）

        TODO: 实现状态树构建和保存功能
        """
        logger.warning("save_state_tree() 暂未实现")
        pass

    def record_executed_step(
        self,
        step: ExplorationStep,
        plan_source: str,
        result_status: str,
        executed_at: str = None
    ):
        """记录实际执行的计划步骤

        Args:
            step: 执行的步骤
            plan_source: 计划来源（"initial_plan" 或 "replan_after_step_X"）
            result_status: 执行结果（"success" 或 "failed"）
            executed_at: 执行时间戳（可选，默认当前时间）
        """
        if executed_at is None:
            executed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        step_record = {
            "step_id": step.step_id,
            "instruction": step.instruction,
            "sub_goal": step.sub_goal,
            "plan_source": plan_source,
            "executed_at": executed_at,
            "result_status": result_status,
            "enable_reflection": step.enable_reflection,
            "max_iterations": step.max_iterations
        }

        self.executed_plan_steps.append(step_record)
        logger.debug(f"记录实际执行步骤: {step.step_id} from {plan_source}")

    def save_executed_plan(self):
        """保存实际执行的计划到文件"""
        executed_plan_file = self.output_dir / "executed_plan.json"

        executed_plan_data = {
            "description": "记录从头到尾实际执行的每个步骤的计划（来自初始计划或各次replan后的第一步）",
            "total_steps": len(self.executed_plan_steps),
            "steps": self.executed_plan_steps,
            "generated_at": datetime.now().isoformat()
        }

        with open(executed_plan_file, 'w', encoding='utf-8') as f:
            json.dump(executed_plan_data, f, indent=2, ensure_ascii=False)

        logger.success(f"✓ 实际执行计划已保存: {executed_plan_file}")
        logger.info(f"  - 总步骤数: {len(self.executed_plan_steps)}")

