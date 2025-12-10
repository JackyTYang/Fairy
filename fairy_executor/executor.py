"""
核心执行器模块

重构后的FairyExecutor，提供清晰的接口和模块化设计
"""

import time
from datetime import datetime
from typing import List, Dict, Optional

from Citlali.models.entity import ChatMessage
from Citlali.models.openai.client import OpenAIChatClient
from Fairy.entity.info_entity import ScreenInfo, ActionInfo, PlanInfo
from Fairy.tools.mobile_controller.action_type import AtomicActionType, ATOMIC_ACTION_SIGNITURES
from Fairy.tools.mobile_controller.ui_automator_tools.mobile_control_tool import UiAutomatorMobileController
from Fairy.tools.mobile_controller.ui_automator_tools.screen_capture_tool import UiAutomatorMobileScreenCapturer
from Fairy.tools.screen_perceptor.ssip_new.perceptor.perceptor import ScreenStructuredInfoPerception

from .config import ExecutorConfig
from .output import ExecutionOutput, OutputManager
from .logger import get_logger

logger = get_logger("FairyExecutor")


class FairyExecutor:
    """
    Fairy移动端自动化执行器

    功能：将自然语言指令转换为具体的移动端操作并执行

    Examples:
        # 基本使用
        config = ExecutorConfig.from_env()
        executor = FairyExecutor(config)

        result = await executor.execute(
            instruction="点击游戏按钮",
            plan_context={
                "overall_plan": "进入游戏页面",
                "current_sub_goal": "点击游戏按钮"
            }
        )

        print(f"执行成功: {result.success}")
        print(f"输出文件: {result.output_files}")

        # 传递给其他agent
        next_agent.process(result)
    """

    def __init__(self, config: ExecutorConfig):
        """
        初始化执行器

        Args:
            config: 执行器配置对象
        """
        self.config = config
        logger.info(f"初始化FairyExecutor，设备: {config.device.device_id}")

        # 初始化模型客户端
        self.model_client = OpenAIChatClient({
            "model": config.core_model.model_name,
            "api_key": config.core_model.api_key,
            "base_url": config.core_model.api_base,
            "temperature": config.core_model.temperature
        })

        # 初始化底层工具
        fairy_config = self._create_fairy_config()
        self.controller = UiAutomatorMobileController(fairy_config)
        self.screen_capturer = UiAutomatorMobileScreenCapturer(fairy_config)

        # 初始化屏幕感知器
        if config.perception.visual_model:
            self.screen_perceptor = ScreenStructuredInfoPerception(
                config.perception.visual_model,
                config.perception.text_summary_model
            )
            logger.info("屏幕感知器已启用")
        else:
            self.screen_perceptor = None
            logger.warning("屏幕感知器未配置")

        # 初始化输出管理器
        self.output_manager = OutputManager(config.output.output_dir)
        logger.info(f"输出目录: {self.output_manager.session_dir}")

    def _create_fairy_config(self):
        """创建Fairy配置对象（Mock）"""
        class MockFairyConfig:
            def __init__(self, device_config):
                self.device = device_config.device_id
                self.temp_path = device_config.temp_path
                self.screenshot_phone_path = device_config.screenshot_phone_path
                self.screenshot_filename = device_config.screenshot_filename
                self.task_temp_path = device_config.temp_path

            def get_screenshot_temp_path(self):
                return self.temp_path

        return MockFairyConfig(self.config.device)

    async def execute(
        self,
        instruction: str,
        plan_context: Optional[Dict] = None,
        historical_actions: Optional[List[Dict]] = None,
        execution_tips: str = "",
        key_infos: Optional[List] = None,
        language: str = "Chinese"
    ) -> ExecutionOutput:
        """
        执行自然语言指令

        Args:
            instruction: 自然语言指令，如 "点击游戏按钮"
            plan_context: 计划上下文，包含:
                - overall_plan: 整体计划
                - current_sub_goal: 当前子目标
            historical_actions: 历史动作列表（可选）
            execution_tips: 执行建议（可选）
            key_infos: 关键信息列表（可选）
            language: 指令语言

        Returns:
            ExecutionOutput: 执行结果，包含所有输出文件路径
        """
        start_time = time.time()
        execution_id = self.output_manager.get_execution_id()

        logger.info(f"[{execution_id}] 开始执行指令: {instruction}")

        try:
            # 1. 获取屏幕信息
            logger.info(f"[{execution_id}] 获取屏幕信息...")
            screen_before = await self._get_screen_info()

            # 保存截图和标记图像
            output_files = {}
            if self.config.output.save_screenshots:
                screenshot_path = self.output_manager.save_screenshot(screen_before, "before", execution_id)
                output_files['screenshot_before'] = str(screenshot_path)
                logger.debug(f"[{execution_id}] 截图已保存: {screenshot_path}")

            if self.config.output.save_marked_images and screen_before.perception_infos.use_set_of_marks_mapping:
                marked_path = self.output_manager.save_marked_image(screen_before, "before", execution_id)
                mapping_path = self.output_manager.save_mark_mapping(screen_before, "before", execution_id)
                output_files['marked_image_before'] = str(marked_path)
                output_files['mark_mapping_before'] = str(mapping_path)
                logger.debug(f"[{execution_id}] 标记图像已保存: {marked_path}")

            # 2. 构建计划信息
            if plan_context is None:
                plan_context = {
                    "overall_plan": instruction,
                    "current_sub_goal": instruction
                }

            plan_info = PlanInfo(
                plan_thought="",
                overall_plan=plan_context.get("overall_plan", instruction),
                current_sub_goal=plan_context.get("current_sub_goal", instruction),
                user_interaction_type="0",
                user_interaction_thought=""
            )

            # 3. LLM决策动作
            logger.info(f"[{execution_id}] LLM决策中...")
            action_info = await self._decide_action(
                instruction=instruction,
                language=language,
                plan_info=plan_info,
                screen_info=screen_before,
                historical_actions=historical_actions or [],
                execution_tips=execution_tips,
                key_infos=key_infos or []
            )

            if action_info is None:
                raise Exception("LLM决策失败")

            logger.info(f"[{execution_id}] 决策完成，准备执行 {len(action_info.actions)} 个动作")

            # 4. 执行动作
            await self._execute_actions(action_info.actions)
            logger.success(f"[{execution_id}] 动作执行完成")

            # 5. 获取执行后的屏幕信息
            screen_after = await self._get_screen_info()

            if self.config.output.save_screenshots:
                screenshot_path = self.output_manager.save_screenshot(screen_after, "after", execution_id)
                output_files['screenshot_after'] = str(screenshot_path)

            if self.config.output.save_marked_images and screen_after.perception_infos.use_set_of_marks_mapping:
                marked_path = self.output_manager.save_marked_image(screen_after, "after", execution_id)
                mapping_path = self.output_manager.save_mark_mapping(screen_after, "after", execution_id)
                output_files['marked_image_after'] = str(marked_path)
                output_files['mark_mapping_after'] = str(mapping_path)

            # 6. 构建执行结果
            execution_time = time.time() - start_time
            result = ExecutionOutput(
                success=True,
                instruction=instruction,
                actions_taken=action_info.actions,
                action_thought=action_info.action_thought,
                action_expectation=action_info.action_expectation,
                execution_time=execution_time,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                output_files=output_files,
                screen_before=screen_before,
                screen_after=screen_after
            )

            # 保存执行结果
            result_path = self.output_manager.save_execution_result(result)
            output_files['result'] = str(result_path)

            logger.success(f"[{execution_id}] 执行成功，耗时 {execution_time:.2f}秒")
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[{execution_id}] 执行失败: {e}")

            result = ExecutionOutput(
                success=False,
                instruction=instruction,
                actions_taken=[],
                action_thought="",
                action_expectation="",
                execution_time=execution_time,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                output_files=output_files if 'output_files' in locals() else {},
                screen_before=screen_before if 'screen_before' in locals() else None,
                error=str(e)
            )

            # 保存失败结果
            result_path = self.output_manager.save_execution_result(result)
            result.output_files['result'] = str(result_path)

            return result

    async def _get_screen_info(self) -> ScreenInfo:
        """获取屏幕信息"""
        import time

        # 获取当前Activity
        t0 = time.time()
        activity_info = await self.screen_capturer.get_current_activity()
        logger.debug(f"获取Activity耗时: {time.time() - t0:.2f}秒")

        # 获取截图和UI层次结构
        t0 = time.time()
        screenshot_file_info, ui_hierarchy_xml = await self.screen_capturer.get_screen()
        logger.debug(f"获取截图和UI层次耗时: {time.time() - t0:.2f}秒")

        t0 = time.time()
        screenshot_file_info.compress_image_to_jpeg()
        logger.debug(f"压缩图像耗时: {time.time() - t0:.2f}秒")

        # 获取键盘状态
        t0 = time.time()
        keyboard_status = await self.screen_capturer.get_keyboard_activation_status()
        logger.debug(f"获取键盘状态耗时: {time.time() - t0:.2f}秒")

        # 解析屏幕
        if self.screen_perceptor is not None:
            t0 = time.time()
            logger.info(f"开始屏幕感知解析...")
            screenshot_file_info, perception_infos = await self.screen_perceptor.get_perception_infos(
                screenshot_file_info,
                ui_hierarchy_xml,
                non_visual_mode=self.config.perception.non_visual_mode,
                target_app=activity_info.package_name
            )
            logger.info(f"屏幕感知解析完成，耗时: {time.time() - t0:.2f}秒")
            perception_infos.keyboard_status = keyboard_status[1] == "true"
        else:
            # 如果没有感知器，创建一个简单的感知信息
            from Fairy.tools.screen_perceptor.ssip_new.perceptor.entity import SSIPInfo
            perception_infos = SSIPInfo(
                width=1080,
                height=1920,
                perception_infos=[ui_hierarchy_xml, None],
                non_visual_mode=True,
                SoM_mapping=None
            )
            perception_infos.keyboard_status = keyboard_status[1] == "true"

        return ScreenInfo(screenshot_file_info, perception_infos, activity_info)

    async def _decide_action(
        self,
        instruction: str,
        language: str,
        plan_info: PlanInfo,
        screen_info: ScreenInfo,
        historical_actions: List[Dict],
        execution_tips: str,
        key_infos: List
    ) -> Optional[ActionInfo]:
        """使用LLM决策动作"""
        import time

        # 构建Prompt
        t0 = time.time()
        prompt = self._build_action_decision_prompt(
            instruction=instruction,
            language=language,
            plan_info=plan_info,
            screen_info=screen_info,
            historical_actions=historical_actions,
            execution_tips=execution_tips,
            key_infos=key_infos
        )
        logger.debug(f"Prompt构建耗时: {time.time() - t0:.2f}秒, 长度: {len(prompt)}字符")

        # 准备图像
        t0 = time.time()
        images = []
        if not self.config.perception.non_visual_mode:
            images.append(screen_info.screenshot_file_info.get_screenshot_Image_file())
        logger.debug(f"图像准备耗时: {time.time() - t0:.2f}秒, 图像数: {len(images)}")

        # 构建消息
        system_message = ChatMessage(
            content="You are part of a helpful AI assistant for operating mobile phones and your identity is an action decider. Your goal is to choose the correct atomic actions to complete the user's instruction. Think as if you are a human user operating the phone.",
            type="SystemMessage"
        )

        user_message = ChatMessage(
            content=[prompt] + images,
            type="UserMessage",
            source="user"
        )

        # 调用LLM
        try:
            t0 = time.time()
            logger.info(f"开始调用LLM API...")
            response = await self.model_client.create([system_message, user_message])
            llm_time = time.time() - t0
            logger.info(f"LLM API调用完成，耗时: {llm_time:.2f}秒")
            logger.debug(f"LLM响应长度: {len(response.content)}字符")
            logger.debug(f"LLM响应内容: {response.content[:200]}...")
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return None

        # 解析响应
        t0 = time.time()
        action_info = self._parse_action_response(response.content, screen_info)
        logger.debug(f"响应解析耗时: {time.time() - t0:.2f}秒")

        return action_info

    def _build_action_decision_prompt(
        self,
        instruction: str,
        language: str,
        plan_info: PlanInfo,
        screen_info: ScreenInfo,
        historical_actions: List[Dict],
        execution_tips: str,
        key_infos: List
    ) -> str:
        """构建动作决策的Prompt"""
        # 基本信息
        prompt = f"---\n" \
                 f"- Instruction: {instruction}\n" \
                 f"- Overall Plan: {plan_info.overall_plan}\n" \
                 f"- Current Sub-goal: {plan_info.current_sub_goal}\n" \
                 f"- Key Information Record (Excluding Current Screen): {key_infos}\n" \
                 f"\n"

        # 屏幕信息
        prompt += f"---\n"
        if not self.config.perception.non_visual_mode:
            screenshot_prompt = "The attached image is a screenshots of your phone to show the current state"
        else:
            screenshot_prompt = "The following text description (e.g. JSON or XML) is converted from a screenshots of your phone to show the current state"

        prompt += screen_info.perception_infos.get_screen_info_note_prompt(screenshot_prompt)
        prompt += f"\n"
        prompt += screen_info.perception_infos.get_screen_info_prompt()

        prompt += f"Please scrutinize the above screen information to infer the type of the current page (e.g., home page, search page, results page, details page, etc.) and thus the main function of the page. This helps you to avoid wrong actions.\n"

        # 动作选择指导
        prompt += "---\n"
        prompt += "Carefully examine all the information provided above and decide on the next action to perform. If you notice an unsolved error in the previous action, think as a human user and attempt to rectify them. You must choose your action from ONE or MORE of the atomic actions.\n"
        prompt += "If there are multiple options and the user does not specify which one to choose in the Instruction, interaction with the user is necessary. You cannot make any choices on behalf of the user.\n"
        prompt += "\n"

        # 原子动作列表
        prompt += "- Atomic Actions: \n"
        prompt += "The atomic action functions are listed in the format of `name(arguments): description` as follows:\n"

        use_som = screen_info.perception_infos.use_set_of_marks_mapping
        for action, value in ATOMIC_ACTION_SIGNITURES.items():
            if use_som:
                prompt += f"- {action}({', '.join(value['SoM_arguments'])}): {value['description'](True)}\n"
            else:
                prompt += f"- {action}({', '.join(value['arguments'])}): {value['description'](False)}\n"

        prompt += f"IMPORTANT: When you input something (especially a search), please be careful to use the language {language}.\n\n"

        if not screen_info.perception_infos.keyboard_status:
            prompt += "NOTE: Unable to input. The keyboard has not been activated. To input, please activate the keyboard by tapping on an input box, which includes tapping on an input box first.\n\n"

        # 历史动作
        prompt += f"---\n- Latest Action History: \n"
        if len(historical_actions) > 0:
            prompt += "(Recent actions you took previously)\n"
            for action in historical_actions[-5:]:
                prompt += f"Action: {action}\n"
            prompt += "\n"
        else:
            prompt += "No actions have been taken yet.\n\n"

        # 执行Tips
        if execution_tips:
            prompt += f"---\n"
            prompt += f"Here's some TIPS for execution the action. These TIPS are VERY IMPORTANT, so MAKE SURE you follow them to the letter!\n"
            prompt += f"{execution_tips}\n\n"

        # 输出格式
        prompt += "---\n"
        prompt += "Please provide a JSON with 4 keys, which are interpreted as follows:\n"
        prompt += "- action_thought: A detailed explanation of your rationale for the chosen action.\n"
        prompt += "- actions: ONE or MORE action from the 'Atomic Actions' provided. IMPORTANT: DO NOT return invalid actions like null or stop. DO NOT repeat previously failed actions. The decided action must be provided in a valid JSON format and should be an array containing a sequence of actions, specifying the name and parameters of the action. For example, if you decide to tap on position (100, 200) first, you should first put in the array {\"name\":\"Tap\", \"arguments\":{\"x\":100, \"y\":100}}. If an action does not require parameters, such as 'Wait', fill in the 'Parameters' field with null. IMPORTANT: MAKE SURE the parameter key matches the signature of the action function exactly. MAKE SURE that the order of the actions in the array is the same as the order in which you want them to be executed. MAKE SURE this JSON can be loaded correctly by json.load().\n"
        prompt += "- action_expectation: A brief description of the expected results of the selected action(s).\n"
        prompt += "- user_interaction_thought: A judgment on whether or not need to interact with the user and explain the reasons.\n"
        prompt += "Make sure this JSON can be loaded correctly by json.load().\n"

        return prompt

    def _parse_action_response(self, response: str, screen_info: ScreenInfo) -> Optional[ActionInfo]:
        """解析LLM的动作决策响应"""
        try:
            # 提取JSON
            if "json" in response:
                import re
                response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)

            import json
            response_json = json.loads(response)

            # 验证动作
            valid_action_names = [action_type.value for action_type in AtomicActionType]
            logger.debug(f"有效的动作名称: {valid_action_names}")

            for action in response_json['actions']:
                action_name = action['name']

                # 清理动作名称（移除可能的前缀）
                if 'AtomicActionType.' in action_name:
                    action_name = action_name.replace('AtomicActionType.', '')
                    action['name'] = action_name
                    logger.warning(f"修正动作名称: {action['name']} -> {action_name}")

                if action_name not in valid_action_names:
                    logger.error(f"无效的动作名称: {action_name}")
                    logger.error(f"有效的动作名称列表: {valid_action_names}")
                    logger.error(f"完整响应: {response}")
                    return None

            # SoM坐标转换
            actions = response_json['actions']
            if screen_info.perception_infos.use_set_of_marks_mapping:
                logger.debug(f"LLM返回的原始动作（带标记号）: {actions}")
                actions = self._convert_som_to_coordinates(
                    actions,
                    screen_info.perception_infos.convert_marks_to_coordinates
                )
                logger.debug(f"转换后的动作（带坐标）: {actions}")

            return ActionInfo(
                action_thought=response_json['action_thought'],
                actions=actions,
                action_expectation=response_json['action_expectation'],
                user_interaction_thought=response_json['user_interaction_thought']
            )

        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            logger.debug(f"响应内容: {response}")
            return None

    def _convert_som_to_coordinates(self, actions: List[Dict], convert_func) -> List[Dict]:
        """将Set-of-Marks标记号转换为坐标"""
        converted_actions = []

        for action in actions:
            action_type = AtomicActionType(action['name'])

            if action_type == AtomicActionType.Tap:
                mark_number = action['arguments']['mark_number']
                coordinate = convert_func(mark_number)
                if coordinate:
                    converted_actions.append({
                        'name': action['name'],
                        'arguments': {'x': coordinate[0], 'y': coordinate[1]}
                    })
                else:
                    logger.warning(f"标记 #{mark_number} 转换失败，动作被丢弃")

            elif action_type == AtomicActionType.LongPress:
                mark_number = action['arguments']['mark_number']
                coordinate = convert_func(mark_number)
                if coordinate:
                    converted_actions.append({
                        'name': action['name'],
                        'arguments': {
                            'x': coordinate[0],
                            'y': coordinate[1],
                            'duration': action['arguments']['duration']
                        }
                    })
                else:
                    logger.warning(f"标记 #{mark_number} 转换失败，动作被丢弃")

            elif action_type == AtomicActionType.Swipe:
                mark_number = action['arguments']['mark_number']
                result = convert_func(mark_number)
                if result:
                    try:
                        # 尝试解包为边界
                        (x1, y1), (x2, y2) = result
                        center_x = (x1 + x2) / 2
                        center_y = (y1 + y2) / 2
                        width = x2 - x1
                        height = y2 - y1
                    except (TypeError, ValueError) as e:
                        # 如果解包失败，说明返回的是坐标而不是边界
                        # 使用坐标作为中心点，使用默认的宽高
                        logger.warning(f"标记 #{mark_number} 返回的是坐标而不是边界: {result}，使用默认滑动距离")
                        if isinstance(result, (list, tuple)) and len(result) == 2:
                            center_x, center_y = result
                            # 使用默认的滑动距离（500像素）
                            width = 500
                            height = 500
                        else:
                            logger.error(f"无法解析标记 #{mark_number} 的返回值: {result}，动作被丢弃")
                            continue

                    distance = action['arguments']['distance']
                    duration = action['arguments']['duration']
                    direction = action['arguments']['direction']

                    if direction == 'H':
                        # 垂直滑动
                        dy = height * abs(distance) / 2
                        start_y = center_y + dy if distance > 0 else center_y - dy
                        end_y = center_y - dy if distance > 0 else center_y + dy
                        swipe_action = {
                            'name': action['name'],
                            'arguments': {
                                'x1': center_x, 'y1': start_y,
                                'x2': center_x, 'y2': end_y,
                                'duration': duration
                            }
                        }
                        logger.info(f"Swipe动作转换: 标记#{mark_number} -> 垂直滑动 ({center_x:.0f}, {start_y:.0f}) -> ({center_x:.0f}, {end_y:.0f})")
                        converted_actions.append(swipe_action)
                    elif direction == 'W':
                        # 水平滑动
                        dx = width * abs(distance) / 2
                        start_x = center_x + dx if distance > 0 else center_x - dx
                        end_x = center_x - dx if distance > 0 else center_x + dx
                        swipe_action = {
                            'name': action['name'],
                            'arguments': {
                                'x1': start_x, 'y1': center_y,
                                'x2': end_x, 'y2': center_y,
                                'duration': duration
                            }
                        }
                        logger.info(f"Swipe动作转换: 标记#{mark_number} -> 水平滑动 ({start_x:.0f}, {center_y:.0f}) -> ({end_x:.0f}, {center_y:.0f})")
                        converted_actions.append(swipe_action)
                else:
                    logger.warning(f"标记 #{mark_number} 转换失败，动作被丢弃")
            else:
                # 其他动作不需要转换
                converted_actions.append(action)

        return converted_actions

    async def _execute_actions(self, actions: List[Dict]) -> None:
        """执行动作序列"""
        if not actions:
            logger.warning("动作列表为空，无操作执行")
            return

        logger.info(f"执行 {len(actions)} 个动作")
        for i, action in enumerate(actions, 1):
            logger.info(f"动作 {i}: {action['name']} - 参数: {action.get('arguments', {})}")

        await self.controller.execute_actions(actions)

    def get_session_summary(self) -> Dict:
        """获取会话摘要"""
        return self.output_manager.get_session_summary()
