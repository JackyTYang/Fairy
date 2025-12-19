"""
Explorer 核心模块

协调Planner、Perceptor、Executor和StateTracker，实现完整的探索流程
"""

import time
from datetime import datetime
from pathlib import Path

from Fairy.config.model_config import ModelConfig

# 导入Executor
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from Executor import ExecutorConfig, FairyExecutor

from .config import ExplorerConfig
from .entities import ExplorationTarget, ExplorationPlan, ExplorationResult, ExplorationStep
from .planner import ExplorationPlanner
from .perception_wrapper import PerceptionWrapper
from .state_tracker import StateTracker
from .logger import get_logger

logger = get_logger("FairyExplorer")


class FairyExplorer:
    """Fairy功能探索器"""

    def __init__(self, config: ExplorerConfig):
        self.config = config
        logger.info("初始化 FairyExplorer...")

        # 创建会话目录
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = config.output_dir / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"会话目录: {self.session_dir}")

        # 初始化Executor
        executor_config = ExecutorConfig.from_env()
        self.executor = FairyExecutor(executor_config)
        logger.info("Executor已初始化")

        # 初始化Perceptor
        visual_model_config = ModelConfig(
            model_name=config.visual_model_name,
            model_temperature=0,
            model_info={"vision": True, "function_calling": False, "json_output": False},
            api_base=config.visual_api_base,
            api_key=config.visual_api_key
        )
        self.perceptor = PerceptionWrapper(
            visual_model_config=visual_model_config,
            adb_path=config.adb_path,
            output_dir=str(self.session_dir / "perceptor_temp"),
            device_id=config.device_id
        )
        logger.info("Perceptor已初始化")

        # 初始化Planner
        self.planner = ExplorationPlanner(config)
        logger.info("Planner已初始化")

        # 初始化StateTracker
        self.state_tracker = StateTracker(self.session_dir)
        logger.info("StateTracker已初始化")

        logger.success("FairyExplorer初始化完成")

    async def explore(self, target: ExplorationTarget) -> ExplorationResult:
        """执行功能探索"""
        start_time = time.time()
        logger.info(f"开始探索: {target.app_name} - {target.feature_to_explore}")

        try:
            # 阶段1: 初始化
            logger.info("=" * 60)
            logger.info("阶段1: 初始化")
            logger.info("=" * 60)

            initial_perception = await self.perceptor.capture_and_perceive(
                non_visual_mode=False,
                target_app=target.app_package
            )
            logger.success("初始屏幕捕获完成")

            current_plan = await self.planner.create_initial_plan(target, initial_perception)
            logger.success(f"初始计划生成完成，共 {len(current_plan.steps)} 个步骤")
            current_plan.save_to_file(self.session_dir / "initial_plan.json")

            # 阶段2: 执行循环
            logger.info("=" * 60)
            logger.info("阶段2: 执行循环")
            logger.info("=" * 60)

            total_steps_executed = 0
            failed_steps = 0

            while total_steps_executed < self.config.max_exploration_steps:
                next_step = self.planner.get_next_step(current_plan)
                if next_step is None:
                    logger.info("没有更多待执行的步骤")
                    break

                total_steps_executed += 1
                logger.info(f"\n{'=' * 60}")
                logger.info(f"执行步骤 {total_steps_executed}: {next_step.step_id}")
                logger.info(f"指令: {next_step.instruction}")
                logger.info(f"{'=' * 60}")

                next_step.status = "executing"

                current_perception = await self.perceptor.capture_and_perceive(
                    non_visual_mode=False,
                    target_app=target.app_package
                )

                executor_result = await self.executor.execute(
                    instruction=next_step.instruction,
                    plan_context={
                        "overall_plan": current_plan.overall_plan,
                        "current_sub_goal": next_step.sub_goal
                    },
                    enable_reflection=next_step.enable_reflection,
                    max_iterations=next_step.max_iterations
                )

                executor_result_dict = executor_result.to_dict()

                # ⭐ 将Executor执行后的screen_after转换为PerceptionOutput（包含双截图）
                if executor_result.screen_after:
                    logger.info("将Executor执行后的双截图转换为PerceptionOutput...")
                    after_perception = await self._convert_screen_info_to_perception(executor_result.screen_after)
                else:
                    logger.warning("Executor未返回screen_after，使用执行前的perception")
                    after_perception = current_perception

                snapshot = await self.state_tracker.record_step(
                    step=next_step,
                    perception_output=after_perception,  # ⭐ 使用执行后的perception（含双截图）
                    executor_result=executor_result_dict
                )

                if executor_result.success:
                    next_step.status = "completed"
                    logger.success(f"步骤 {next_step.step_id} 执行成功")
                    if executor_result.progress_info and executor_result.progress_info.action_result == "A":
                        page_name = next_step.sub_goal
                        self.state_tracker.update_navigation_path(page_name)
                else:
                    next_step.status = "failed"
                    failed_steps += 1
                    logger.error(f"步骤 {next_step.step_id} 执行失败")

                if self._should_replan(total_steps_executed, next_step, executor_result_dict):
                    logger.info("触发重新规划...")

                    # 使用Executor执行后的屏幕信息进行重新规划
                    # Executor已经在执行后立刻捕获了屏幕，包括短暂的toast等提示
                    if executor_result.screen_after:
                        logger.info("使用Executor执行后的屏幕信息进行重新规划...")
                        # 从ScreenInfo转换为PerceptionOutput
                        replan_perception = await self._convert_screen_info_to_perception(executor_result.screen_after)
                    else:
                        # 兜底：如果Executor没有返回执行后屏幕，重新捕获
                        logger.warning("Executor未返回执行后屏幕，重新捕获...")
                        replan_perception = await self.perceptor.capture_and_perceive(
                            non_visual_mode=False,
                            target_app=target.app_package
                        )

                    current_plan = await self.planner.replan(
                        target,
                        current_plan,
                        replan_perception,
                        next_step,
                        executor_result_dict,
                        self.state_tracker.get_current_path()
                    )
                    logger.success(f"重新规划完成，新计划包含 {len(current_plan.steps)} 个步骤")
                    current_plan.save_to_file(self.session_dir / f"plan_after_step_{next_step.step_id}.json")

            # 阶段3: 结束
            logger.info("=" * 60)
            logger.info("阶段3: 探索完成")
            logger.info("=" * 60)

            self.state_tracker.save_navigation_path()
            current_plan.save_to_file(self.session_dir / "final_plan.json")

            total_time = time.time() - start_time
            completed_steps = len([s for s in current_plan.steps if s.status == "completed"])

            result = ExplorationResult(
                success=True,
                target=target,
                final_plan=current_plan,
                execution_history=self.state_tracker.get_execution_history(),
                total_steps=total_steps_executed,
                completed_steps=completed_steps,
                failed_steps=failed_steps,
                total_time=total_time,
                output_dir=str(self.session_dir)
            )

            result.save_to_file(self.session_dir / "exploration_result.json")

            logger.success("=" * 60)
            logger.success(f"探索完成！")
            logger.success(f"总步骤数: {total_steps_executed}")
            logger.success(f"输出目录: {self.session_dir}")
            logger.success("=" * 60)

            return result

        except Exception as e:
            logger.error(f"探索过程中发生错误: {e}")
            import traceback
            logger.error(traceback.format_exc())

            total_time = time.time() - start_time
            result = ExplorationResult(
                success=False,
                target=target,
                final_plan=current_plan if 'current_plan' in locals() else None,
                execution_history=self.state_tracker.get_execution_history(),
                total_steps=total_steps_executed if 'total_steps_executed' in locals() else 0,
                completed_steps=0,
                failed_steps=failed_steps if 'failed_steps' in locals() else 0,
                total_time=total_time,
                output_dir=str(self.session_dir),
                error=str(e)
            )

            result.save_to_file(self.session_dir / "exploration_result.json")
            return result

    def _should_replan(self, steps_executed: int, last_step: ExplorationStep, last_result: dict) -> bool:
        """判断是否需要重新规划"""
        if self.config.replan_on_every_step:
            return True
        else:
            return steps_executed % self.config.replan_interval == 0

    async def _convert_screen_info_to_perception(self, screen_info) -> "PerceptionOutput":
        """将Fairy的ScreenInfo转换为Explorer的PerceptionOutput

        Args:
            screen_info: Fairy的ScreenInfo对象

        Returns:
            PerceptionOutput对象
        """
        from .entities import PerceptionOutput
        from Perceptor.tools import XMLCompressor
        import os
        import json

        # 获取截图路径（稳定截图，5秒）
        screenshot_path = screen_info.screenshot_file_info.get_screenshot_fullpath()
        marked_screenshot_path = screenshot_path  # SoM标记后的图也是同一个文件

        # 获取UI XML字符串（从perception_infos.infos[0]获取）
        ui_xml_str = screen_info.perception_infos.infos[0]
        timestamp = screen_info.screenshot_file_info.file_build_timestamp

        # 创建临时目录保存XML和压缩文件
        temp_dir = Path(screenshot_path).parent
        xml_path = temp_dir / f"ui_dump_{timestamp}.xml"

        # 保存原始XML（稳定截图）
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(ui_xml_str)

        # 压缩XML（稳定截图）
        compressor = XMLCompressor(output_dir=str(temp_dir))
        compressed_xml_path, compressed_txt_path = await compressor.compress_xml(
            ui_xml=ui_xml_str, timestamp=timestamp
        )

        # 保存SoM映射
        som_mapping_path = temp_dir / f"som_mapping_{timestamp}.json"
        with open(som_mapping_path, 'w', encoding='utf-8') as f:
            json.dump(screen_info.perception_infos.SoM_mapping, f, indent=2)

        # 获取屏幕尺寸
        screen_size = (
            screen_info.perception_infos.width,
            screen_info.perception_infos.height
        )

        # ⭐ 检查是否有立刻截图（0.2秒）及其完整信息
        immediate_screenshot_path = None
        immediate_marked_screenshot_path = None
        immediate_xml_path = None
        immediate_compressed_xml_path = None
        immediate_compressed_txt_path = None
        immediate_som_mapping_path = None

        if hasattr(screen_info, 'immediate_screenshot_path') and screen_info.immediate_screenshot_path:
            immediate_screenshot_path = screen_info.immediate_screenshot_path

            # ⭐ 提取immediate截图的标记后截图路径
            if hasattr(screen_info, 'immediate_marked_screenshot_path'):
                immediate_marked_screenshot_path = screen_info.immediate_marked_screenshot_path

            # 保存立刻截图的XML
            if hasattr(screen_info, 'immediate_xml') and screen_info.immediate_xml:
                immediate_xml_path = temp_dir / f"ui_dump_{timestamp}_immediate.xml"
                with open(immediate_xml_path, 'w', encoding='utf-8') as f:
                    f.write(screen_info.immediate_xml)

                # 压缩立刻截图的XML
                immediate_compressed_xml_path, immediate_compressed_txt_path = await compressor.compress_xml(
                    ui_xml=screen_info.immediate_xml,
                    timestamp=f"{timestamp}_immediate"
                )
                immediate_xml_path = str(immediate_xml_path)

            # ⭐ 保存immediate截图的SoM映射
            if hasattr(screen_info, 'immediate_perception_infos') and screen_info.immediate_perception_infos:
                immediate_som_mapping_path = temp_dir / f"som_mapping_{timestamp}_immediate.json"
                with open(immediate_som_mapping_path, 'w', encoding='utf-8') as f:
                    json.dump(screen_info.immediate_perception_infos.SoM_mapping, f, indent=2)
                immediate_som_mapping_path = str(immediate_som_mapping_path)

            logger.info(f"检测到双截图模式（完整信息）: immediate={immediate_screenshot_path}, stable={screenshot_path}")

        return PerceptionOutput(
            screenshot_path=screenshot_path,
            marked_screenshot_path=marked_screenshot_path,
            xml_path=str(xml_path),
            compressed_xml_path=compressed_xml_path,
            compressed_txt_path=compressed_txt_path,
            som_mapping_path=str(som_mapping_path),
            timestamp=timestamp,
            screen_size=screen_size,
            immediate_screenshot_path=immediate_screenshot_path,
            immediate_marked_screenshot_path=immediate_marked_screenshot_path,
            immediate_xml_path=immediate_xml_path,
            immediate_compressed_xml_path=immediate_compressed_xml_path,
            immediate_compressed_txt_path=immediate_compressed_txt_path,
            immediate_som_mapping_path=immediate_som_mapping_path
        )
