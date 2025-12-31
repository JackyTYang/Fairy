"""
Explorer 核心模块

协调Planner、Perceptor、Executor和StateTracker，实现完整的探索流程
"""

import time
import signal
import atexit
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
from .state_identifier import StateIdentifier  # ⭐ 新增
from .feature_tree_builder import FeatureTreeBuilder  # ⭐ 新增
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

        # ⭐ 初始化StateIdentifier和FeatureTreeBuilder（延迟到explore()）
        self.state_identifier = StateIdentifier()
        self.feature_tree_builder = None  # 初始计划后创建
        self.current_feature_path = []  # 当前功能路径

        # 初始化Executor
        executor_config = ExecutorConfig.from_env()
        # ⭐ 指定Executor输出到当前session目录的executor_outputs子目录
        executor_config.output.output_dir = self.session_dir / "executor_outputs"
        self.executor = FairyExecutor(executor_config, use_session_subdir=False)
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
        self.planner = ExplorationPlanner(config, session_dir=self.session_dir)
        logger.info("Planner已初始化")

        # 初始化StateTracker
        self.state_tracker = StateTracker(self.session_dir)
        logger.info("StateTracker已初始化")

        # ⭐ 注册信号处理器（捕获Ctrl+C等中断信号）
        self._register_signal_handlers()

        # ⭐ 注册程序退出时的清理函数
        atexit.register(self._cleanup_on_exit)

        logger.success("FairyExplorer初始化完成")

    def _save_feature_tree(self, reason="程序中断"):
        """保存功能状态树（支持中途保存）

        Args:
            reason: 保存原因，用于日志记录
        """
        if self.feature_tree_builder is None:
            logger.warning(f"功能树未初始化，跳过保存（原因: {reason}）")
            return

        try:
            tree_path = self.session_dir / "feature_tree.json"
            updates_path = self.session_dir / "feature_updates.json"

            self.feature_tree_builder.save_tree(tree_path)
            self.feature_tree_builder.save_update_log(updates_path)

            summary = self.feature_tree_builder.get_feature_summary()
            logger.success(f"✓ 功能树已保存（原因: {reason}）")
            logger.info(f"  - 功能树: {tree_path}")
            logger.info(f"  - 更新日志: {updates_path}")
            logger.info(f"  - 状态: {summary}")
        except Exception as e:
            logger.error(f"保存功能树失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _register_signal_handlers(self):
        """注册信号处理器，捕获中断信号"""
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            logger.warning(f"\n{'=' * 60}")
            logger.warning(f"收到信号 {signal_name}，正在保存数据...")
            logger.warning(f"{'=' * 60}")

            # 保存功能树
            self._save_feature_tree(reason=f"收到{signal_name}信号")

            # 保存当前状态
            if hasattr(self, 'state_tracker'):
                try:
                    self.state_tracker.save_navigation_path()
                    logger.success("✓ 导航路径已保存")
                except Exception as e:
                    logger.error(f"保存导航路径失败: {e}")

            logger.warning("数据保存完成，程序即将退出")
            logger.warning(f"输出目录: {self.session_dir}")
            logger.warning(f"{'=' * 60}\n")

            # 退出程序
            import sys
            sys.exit(0)

        # 注册常见的中断信号
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # kill命令

        logger.debug("信号处理器已注册（SIGINT, SIGTERM）")

    def _cleanup_on_exit(self):
        """程序正常退出时的清理函数"""
        # 这里不需要做什么，因为正常流程会在explore()中保存
        # 这个函数主要是为了确保异常退出时有最后的保障
        pass

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

            # ⭐ 初始化功能树构建器
            self.feature_tree_builder = FeatureTreeBuilder(
                root_feature_name=target.feature_to_explore,
                root_feature_description=f"探索{target.app_name}的{target.feature_to_explore}功能"
            )

            # ⭐ 从初始计划中提取功能结构
            if current_plan.feature_structure:
                self.feature_tree_builder.initialize_from_plan(current_plan.feature_structure)
                logger.info(f"功能树初始化完成: {self.feature_tree_builder.get_feature_summary()}")

            # ⭐ 设置当前功能路径
            if current_plan.current_feature:
                self.current_feature_path = current_plan.current_feature.get('feature_path', [target.feature_to_explore])
                logger.info(f"当前功能路径: {' -> '.join(self.current_feature_path)}")

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

                # ⭐ 识别和记录State到功能树
                if executor_result.screen_after and self.feature_tree_builder:
                    state_id = self.state_identifier.identify_state(
                        executor_result.screen_after,
                        after_perception
                    )

                    # 生成State名称（简化版，后续可让LLM命名）
                    state_name = self.state_identifier.get_state_name(
                        executor_result.screen_after,
                        state_id
                    )

                    # 添加State到功能树
                    self.feature_tree_builder.add_state(
                        state_id=state_id,
                        state_name=state_name,
                        activity_name=executor_result.screen_after.current_activity_info.activity,
                        perception_output=after_perception,
                        feature_path=self.current_feature_path,
                        step_id=next_step.step_id,
                        instruction=next_step.instruction,
                        actions=executor_result_dict.get('actions_taken', []),
                        success=executor_result.success
                    )

                if executor_result.success:
                    next_step.status = "completed"
                    logger.success(f"步骤 {next_step.step_id} 执行成功")

                    # ⭐ 记录实际执行的步骤（成功）
                    plan_source = "initial_plan" if total_steps_executed == 1 else f"replan_after_step_{total_steps_executed - 1}"
                    self.state_tracker.record_executed_step(
                        step=next_step,
                        plan_source=plan_source,
                        result_status="success"
                    )

                    if executor_result.progress_info and executor_result.progress_info.action_result == "A":
                        page_name = next_step.sub_goal
                        self.state_tracker.update_navigation_path(page_name)
                else:
                    next_step.status = "failed"
                    failed_steps += 1
                    logger.error(f"步骤 {next_step.step_id} 执行失败")

                    # ⭐ 记录实际执行的步骤（失败）
                    plan_source = "initial_plan" if total_steps_executed == 1 else f"replan_after_step_{total_steps_executed - 1}"
                    self.state_tracker.record_executed_step(
                        step=next_step,
                        plan_source=plan_source,
                        result_status="failed"
                    )

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
                        self.state_tracker.get_current_path(),
                        # ⭐ 新增参数：传递功能树和最近状态序列
                        feature_tree=self.feature_tree_builder.tree if self.feature_tree_builder else None,
                        recent_state_sequence=self._get_recent_state_sequence(),
                        step_output_dir=snapshot.step_output_dir  # ⭐ 传递step输出目录
                    )
                    logger.success(f"重新规划完成，新计划包含 {len(current_plan.steps)} 个步骤")
                    current_plan.save_to_file(self.session_dir / f"plan_after_step_{next_step.step_id}.json")

                    # ⭐ 检查是否有功能结构更新
                    if current_plan.feature_update and self.feature_tree_builder:
                        logger.info(f"检测到功能结构更新: {current_plan.feature_update.get('action')}")
                        self.feature_tree_builder.update_feature_structure(
                            feature_update=current_plan.feature_update,
                            step_id=next_step.step_id
                        )

                    # ⭐ 检测功能切换
                    if current_plan.current_feature:
                        new_feature_path = current_plan.current_feature.get('feature_path', [])
                        if new_feature_path != self.current_feature_path:
                            logger.info(f"功能切换: {self.current_feature_path} -> {new_feature_path}")

                            # ⭐ 标记前一个功能为completed
                            if self.current_feature_path and len(self.current_feature_path) > 1:
                                self.feature_tree_builder.mark_feature_completed(
                                    self.current_feature_path,
                                    next_step.step_id
                                )

                            # 如果是新功能，确保已添加到树中
                            if current_plan.current_feature.get('is_new_feature'):
                                logger.info(f"✓ 新功能已添加: {new_feature_path[-1]}")

                            self.current_feature_path = new_feature_path
                            logger.info(f"当前功能路径: {' -> '.join(self.current_feature_path)}")

            # 阶段3: 结束
            logger.info("=" * 60)
            logger.info("阶段3: 探索完成")
            logger.info("=" * 60)

            self.state_tracker.save_navigation_path()
            # ⭐ 保存实际执行计划
            self.state_tracker.save_executed_plan()
            current_plan.save_to_file(self.session_dir / "final_plan.json")

            # ⭐ 保存功能树和更新日志
            self._save_feature_tree(reason="正常完成")

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

            # ⭐ 异常情况下也保存功能树
            self._save_feature_tree(reason=f"异常退出: {type(e).__name__}")

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

    def _get_recent_state_sequence(self):
        """获取最近10个状态ID序列

        Returns:
            List[str]: 状态ID列表，如 ["state_xxx", "state_yyy", ...]
        """
        if not self.feature_tree_builder:
            return []

        # 从feature_tree的state_transitions中提取最近10个状态ID
        # state_transitions的格式是: (from_state_id, to_state_id, step_id)
        transitions = self.feature_tree_builder.tree.state_transitions
        if not transitions:
            return []

        recent_transitions = transitions[-10:] if len(transitions) >= 10 else transitions
        # trans是tuple: (from_state_id, to_state_id, step_id)
        # trans[1] 是 to_state_id
        return [trans[1] for trans in recent_transitions]

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

        # ⭐ 只有在启用立刻截图且screen_info包含立刻截图时才处理
        if (hasattr(screen_info, 'immediate_screenshot_path') and
            screen_info.immediate_screenshot_path is not None and
            screen_info.immediate_screenshot_path):
            immediate_screenshot_path = screen_info.immediate_screenshot_path

            # ⭐ 提取immediate截图的标记后截图路径
            if hasattr(screen_info, 'immediate_marked_screenshot_path') and screen_info.immediate_marked_screenshot_path:
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
        else:
            logger.info(f"单截图模式: stable={screenshot_path}")

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
