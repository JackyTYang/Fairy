"""
最小化的Fairy执行器 - 独立版本
功能：将自然语言指令映射为具体的移动端操作并执行

核心流程：
1. 获取屏幕信息（截图 + UI结构）
2. LLM决策具体动作（基于指令和屏幕信息）
3. 执行动作
4. 返回执行结果

不依赖：
- Citlali框架
- Memory系统（通过参数传递）
- RAG系统（可选）
"""

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import List, Dict, Optional

from dotenv import load_dotenv

from Citlali.models.entity import ChatMessage
from Citlali.models.openai.client import OpenAIChatClient
from Fairy.config.model_config import ModelConfig
from Fairy.entity.info_entity import ScreenInfo, ActionInfo, PlanInfo
from Fairy.tools.mobile_controller.action_type import AtomicActionType, ATOMIC_ACTION_SIGNITURES
# Fairy核心依赖
from Fairy.tools.mobile_controller.ui_automator_tools.mobile_control_tool import UiAutomatorMobileController
from Fairy.tools.mobile_controller.ui_automator_tools.screen_capture_tool import UiAutomatorMobileScreenCapturer
from Fairy.tools.screen_perceptor.ssip_new.perceptor.perceptor import ScreenStructuredInfoPerception


# ==================== 配置类 ====================

@dataclass
class MinimalExecutorConfig:
    """最小化执行器配置"""
    device: str  # 设备ID
    model_client: any  # LLM客户端（兼容Fairy的接口）

    # 可选配置
    temp_path: str = "../../tmp"
    screenshot_phone_path: str = "/sdcard"
    screenshot_filename: str = "screenshot"

    # 屏幕感知配置（可选）
    visual_prompt_model_config: Optional[any] = None
    text_summarization_model_config: Optional[any] = None
    non_visual_mode: bool = False  # True=纯文本模式，False=使用标记图像


# ==================== 执行结果类 ====================

@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    actions_taken: List[Dict]
    action_thought: str
    action_expectation: str
    screen_before: ScreenInfo
    screen_after: Optional[ScreenInfo] = None
    error: Optional[str] = None


# ==================== 核心执行器 ====================

class MinimalFairyExecutor:
    """
    最小化的Fairy执行器

    功能：将自然语言指令转换为具体的移动端操作并执行

    示例：
        executor = MinimalFairyExecutor(
            device="emulator-5554",
            model_client=your_model_client
        )

        result = await executor.execute_instruction(
            instruction="在当前外卖界面点击购物车",
            plan_context={
                "overall_plan": "浏览商品并查看购物车",
                "current_sub_goal": "点击购物车"
            }
        )

        print(f"成功: {result.success}")
        print(f"执行的动作: {result.actions_taken}")
    """

    def __init__(self, device: str, model_client: any, config: Optional[MinimalExecutorConfig] = None):
        """
        初始化执行器

        Args:
            device: 设备ID
            model_client: LLM客户端，需要实现 async create(messages) 方法
            config: 可选的详细配置
        """
        if config is None:
            config = MinimalExecutorConfig(device=device, model_client=model_client)
        else:
            config.device = device
            config.model_client = model_client

        self.config = config
        self.model_client = model_client

        # 初始化底层工具
        fairy_config = self._create_fairy_config()
        self.controller = UiAutomatorMobileController(fairy_config)
        self.screen_capturer = UiAutomatorMobileScreenCapturer(fairy_config)

        # 初始化屏幕感知器（如果提供了模型配置）
        if config.visual_prompt_model_config is not None or config.non_visual_mode:
            self.screen_perceptor = ScreenStructuredInfoPerception(
                config.visual_prompt_model_config,
                config.text_summarization_model_config
            )
        else:
            self.screen_perceptor = None

    def _create_fairy_config(self):
        """创建Fairy配置对象（Mock）"""
        class MockFairyConfig:
            def __init__(self, config: MinimalExecutorConfig):
                self.device = config.device
                self.temp_path = config.temp_path
                self.screenshot_phone_path = config.screenshot_phone_path
                self.screenshot_filename = config.screenshot_filename
                self.task_temp_path = config.temp_path

            def get_screenshot_temp_path(self):
                return self.temp_path

        return MockFairyConfig(self.config)

    # ==================== 主要接口 ====================

    async def execute_instruction(
        self,
        instruction: str,
        plan_context: Optional[Dict] = None,
        historical_actions: Optional[List[Dict]] = None,
        execution_tips: str = "",
        key_infos: Optional[List] = None,
        language: str = "Chinese"
    ) -> ExecutionResult:
        """
        执行自然语言指令

        Args:
            instruction: 自然语言指令，如 "在当前外卖界面点击购物车"
            plan_context: 计划上下文，包含:
                - overall_plan: 整体计划
                - current_sub_goal: 当前子目标
            historical_actions: 历史动作列表（可选）
            execution_tips: 执行建议（可选，可以从RAG获取）
            key_infos: 关键信息列表（可选）
            language: 指令语言

        Returns:
            ExecutionResult: 执行结果
        """
        print(f"\n🚀 [DEBUG] 开始执行指令: {instruction}")
        print(f"   计划上下文: {plan_context}")
        print(f"   执行建议: {execution_tips}")

        try:
            # 1. 获取屏幕信息
            print(f"   步骤1: 获取屏幕信息...")
            screen_before = await self._get_screen_info()
            print(f"   ✅ 屏幕信息获取成功")

            # 2. 构建计划信息
            print(f"   步骤2: 构建计划信息...")
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
            print(f"   ✅ 计划信息构建成功")

            # 3. LLM决策动作
            print(f"   步骤3: 调用LLM决策动作...")
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
                return ExecutionResult(
                    success=False,
                    actions_taken=[],
                    action_thought="",
                    action_expectation="",
                    screen_before=screen_before,
                    error="Failed to decide action"
                )

            # 4. 执行动作
            await self._execute_actions(action_info.actions)

            # 5. 获取执行后的屏幕信息
            screen_after = await self._get_screen_info()

            return ExecutionResult(
                success=True,
                actions_taken=action_info.actions,
                action_thought=action_info.action_thought,
                action_expectation=action_info.action_expectation,
                screen_before=screen_before,
                screen_after=screen_after
            )

        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(f"\n❌ [ERROR] 执行过程中发生异常:")
            print(error_traceback)
            return ExecutionResult(
                success=False,
                actions_taken=[],
                action_thought="",
                action_expectation="",
                screen_before=screen_before if 'screen_before' in locals() else None,
                error=str(e)
            )

    # ==================== 内部方法 ====================

    async def _get_screen_info(self) -> ScreenInfo:
        """获取屏幕信息"""
        # 获取当前Activity
        activity_info = await self.screen_capturer.get_current_activity()

        # 获取截图和UI层次结构
        screenshot_file_info, ui_hierarchy_xml = await self.screen_capturer.get_screen()
        screenshot_file_info.compress_image_to_jpeg()

        # 获取键盘状态
        keyboard_status = await self.screen_capturer.get_keyboard_activation_status()

        # 解析屏幕（如果配置了感知器）
        if self.screen_perceptor is not None:
            screenshot_file_info, perception_infos = await self.screen_perceptor.get_perception_infos(
                screenshot_file_info,
                ui_hierarchy_xml,
                non_visual_mode=self.config.non_visual_mode,
                target_app=activity_info.package_name
            )
            perception_infos.keyboard_status = keyboard_status[1] == "true"

            # 调试：打印标记映射和保存标记图像
            if perception_infos.use_set_of_marks_mapping and perception_infos.SoM_mapping:
                print(f"\n📍 [DEBUG] 屏幕标记映射（所有标记）:")
                for mark_num in sorted(perception_infos.SoM_mapping.keys()):
                    coords = perception_infos.SoM_mapping[mark_num]
                    print(f"  标记 #{mark_num} -> 坐标 {coords}")

                # 保存标记后的图像用于调试
                import shutil
                marked_image_path = screenshot_file_info.get_screenshot_fullpath()  # 修复：使用fullpath而不是Image对象
                debug_image_path = f"{self.config.temp_path}/debug_marked_screen.jpg"
                shutil.copy(marked_image_path, debug_image_path)
                print(f"\n🖼️  [DEBUG] 标记后的图像已保存到: {debug_image_path}")
                print(f"    请查看图像，确认底部导航栏的标记号是否正确")
                print()
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
        """
        使用LLM决策动作

        这是核心方法，复用了Fairy的AppActionDeciderAgent的逻辑
        """
        print(f"\n🤖 [DEBUG] 开始LLM决策...")
        print(f"   指令: {instruction}")

        # 构建Prompt
        prompt = self._build_action_decision_prompt(
            instruction=instruction,
            language=language,
            plan_info=plan_info,
            screen_info=screen_info,
            historical_actions=historical_actions,
            execution_tips=execution_tips,
            key_infos=key_infos
        )
        print(f"   Prompt长度: {len(prompt)} 字符")

        # 准备图像
        images = []
        if not self.config.non_visual_mode:
            images.append(screen_info.screenshot_file_info.get_screenshot_Image_file())
            print(f"   使用视觉模式，图像路径: {images[0]}")
        else:
            print(f"   使用非视觉模式（纯文本）")

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
        print(f"   正在调用LLM...")
        try:
            response = await self.model_client.create([system_message, user_message])
            print(f"   LLM响应长度: {len(response.content)} 字符")
            print(f"   LLM响应内容:\n{response.content}\n")
        except Exception as e:
            print(f"❌ [ERROR] LLM调用失败: {e}")
            return None

        # 解析响应
        print(f"   正在解析LLM响应...")
        action_info = self._parse_action_response(response.content, screen_info)

        if action_info is None:
            print(f"❌ [ERROR] 解析LLM响应失败，返回None")
        else:
            print(f"✅ [DEBUG] LLM决策成功")

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
        """
        构建动作决策的Prompt

        复用Fairy的AppActionDeciderAgent.build_prompt逻辑
        """
        # 基本信息
        prompt = f"---\n" \
                 f"- Instruction: {instruction}\n" \
                 f"- Overall Plan: {plan_info.overall_plan}\n" \
                 f"- Current Sub-goal: {plan_info.current_sub_goal}\n" \
                 f"- Key Information Record (Excluding Current Screen): {key_infos}\n" \
                 f"\n"

        # 屏幕信息
        prompt += f"---\n"
        if not self.config.non_visual_mode:
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
            for action in historical_actions[-5:]:  # 最近5个
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
        """
        解析LLM的动作决策响应

        复用Fairy的AppActionDeciderAgent.parse_response逻辑
        """
        try:
            # 提取JSON
            if "json" in response:
                response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)

            response_json = json.loads(response)

            # 验证动作
            for action in response_json['actions']:
                if action['name'] not in [action_type.value for action_type in AtomicActionType]:
                    print(f"Error! Invalid action name: {action['name']}")
                    return None

            # SoM坐标转换
            actions = response_json['actions']
            if screen_info.perception_infos.use_set_of_marks_mapping:
                print(f"🔍 [DEBUG] LLM返回的原始动作（带标记号）: {actions}")
                actions = self._convert_som_to_coordinates(
                    actions,
                    screen_info.perception_infos.convert_marks_to_coordinates
                )
                print(f"✅ [DEBUG] 转换后的动作（带坐标）: {actions}")

            return ActionInfo(
                action_thought=response_json['action_thought'],
                actions=actions,
                action_expectation=response_json['action_expectation'],
                user_interaction_thought=response_json['user_interaction_thought']
            )

        except Exception as e:
            print(f"Failed to parse action response: {e}")
            print(f"Response: {response}")
            return None

    def _convert_som_to_coordinates(self, actions: List[Dict], convert_func) -> List[Dict]:
        """
        将Set-of-Marks标记号转换为坐标

        复用Fairy的AppActionDeciderAgent.SoM_args_conversion逻辑
        """
        converted_actions = []

        for action in actions:
            action_type = AtomicActionType(action['name'])

            if action_type == AtomicActionType.Tap:
                mark_number = action['arguments']['mark_number']
                coordinate = convert_func(mark_number)
                print(f"🔄 [DEBUG] 转换标记 #{mark_number} -> 坐标 {coordinate}")
                if coordinate:
                    converted_actions.append({
                        'name': action['name'],
                        'arguments': {'x': coordinate[0], 'y': coordinate[1]}
                    })
                else:
                    print(f"⚠️  [WARNING] 标记 #{mark_number} 转换失败！坐标为None，动作被丢弃")

            elif action_type == AtomicActionType.LongPress:
                mark_number = action['arguments']['mark_number']
                coordinate = convert_func(mark_number)
                print(f"🔄 [DEBUG] 转换标记 #{mark_number} -> 坐标 {coordinate}")
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
                    print(f"⚠️  [WARNING] 标记 #{mark_number} 转换失败！坐标为None，动作被丢弃")

            elif action_type == AtomicActionType.Swipe:
                mark_number = action['arguments']['mark_number']
                bounds = convert_func(mark_number)
                print(f"🔄 [DEBUG] 转换标记 #{mark_number} -> 边界 {bounds}")
                if bounds:
                    (x1, y1), (x2, y2) = bounds
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    width = x2 - x1
                    height = y2 - y1
                    distance = action['arguments']['distance']
                    duration = action['arguments']['duration']
                    direction = action['arguments']['direction']

                    if direction == 'H':
                        dy = height * abs(distance) / 2
                        start_y = center_y + dy if distance > 0 else center_y - dy
                        end_y = center_y - dy if distance > 0 else center_y + dy
                        converted_actions.append({
                            'name': action['name'],
                            'arguments': {
                                'x1': center_x, 'y1': start_y,
                                'x2': center_x, 'y2': end_y,
                                'duration': duration
                            }
                        })
                    elif direction == 'W':
                        dx = width * abs(distance) / 2
                        start_x = center_x + dx if distance > 0 else center_x - dx
                        end_x = center_x - dx if distance > 0 else center_x + dx
                        converted_actions.append({
                            'name': action['name'],
                            'arguments': {
                                'x1': start_x, 'y1': center_y,
                                'x2': end_x, 'y2': center_y,
                                'duration': duration
                            }
                        })
                else:
                    print(f"⚠️  [WARNING] 标记 #{mark_number} 转换失败！边界为None，动作被丢弃")
            else:
                # 其他动作不需要转换
                converted_actions.append(action)

        print(f"📊 [DEBUG] 转换结果: {len(actions)} 个原始动作 -> {len(converted_actions)} 个转换后的动作")
        return converted_actions

    async def _execute_actions(self, actions: List[Dict]) -> None:
        """执行动作序列"""
        if not actions:
            print(f"❌ [ERROR] 动作列表为空！没有可执行的动作")
            return

        print(f"🎯 [DEBUG] 准备执行 {len(actions)} 个动作: {actions}")
        await self.controller.execute_actions(actions)
        print(f"✅ [DEBUG] 动作执行完成")

    # ==================== 便捷方法 ====================

    async def get_current_screen(self) -> ScreenInfo:
        """获取当前屏幕信息（不执行动作）"""
        return await self._get_screen_info()

    async def execute_raw_actions(self, actions: List[Dict]) -> None:
        """直接执行动作（不经过LLM决策）"""
        await self._execute_actions(actions)


# ==================== 使用示例 ====================
async def non_visual_mode_usage():
    """非视觉模式 - 使用文本描述而不是标记图像"""
    load_dotenv()

    core_model_client = OpenAIChatClient({
        "model": os.getenv("CORE_LMM_MODEL_NAME"),
        "api_key": os.getenv("CORE_LMM_API_KEY"),
        "base_url": os.getenv("CORE_LMM_API_BASE")
    })

    visual_model_config = ModelConfig(
        model_name=os.getenv("VISUAL_PROMPT_LMM_API_NAME"),
        model_temperature=0,
        model_info={"vision": True, "function_calling": False, "json_output": False},
        api_base=os.getenv("VISUAL_PROMPT_LMM_API_BASE"),
        api_key=os.getenv("VISUAL_PROMPT_LMM_API_KEY")
    )

    text_summary_config = ModelConfig(
        model_name=os.getenv("RAG_LLM_API_NAME"),
        model_temperature=0,
        model_info={"vision": False, "function_calling": False, "json_output": False},
        api_base=os.getenv("RAG_LLM_API_BASE"),
        api_key=os.getenv("RAG_LLM_API_KEY")
    )

    config = MinimalExecutorConfig(
        device=os.getenv("DEVICE_ID", "10.176.65.211:7421"),
        model_client=core_model_client,
        visual_prompt_model_config=visual_model_config,
        text_summarization_model_config=text_summary_config,
        non_visual_mode=True  # True=使用文本描述模式
    )

    executor = MinimalFairyExecutor(
        device=config.device,
        model_client=config.model_client,
        config=config
    )

    result = await executor.execute_instruction(
        instruction="进入游戏栏目",
        plan_context={
            "overall_plan": "进入游戏栏目",
            "current_sub_goal": "点击游戏tab"
        },
        execution_tips="分类通常在侧面或者下面"
    )

    print(f"执行成功: {result.success}")
    print(f"执行的动作: {result.actions_taken}")

    return result

async def correct_usage():
    """正确的使用方式 - 配置屏幕感知器"""
    load_dotenv()

    # 1. 创建核心模型客户端（用于动作决策）
    core_model_client = OpenAIChatClient({
        "model": os.getenv("CORE_LMM_MODEL_NAME"),
        "api_key": os.getenv("CORE_LMM_API_KEY"),
        "base_url": os.getenv("CORE_LMM_API_BASE")
    })

    # 2. 配置视觉模型（用于屏幕理解）⭐关键！
    visual_model_config = ModelConfig(
        model_name=os.getenv("VISUAL_PROMPT_LMM_API_NAME"),
        model_temperature=0,
        model_info={"vision": True, "function_calling": False, "json_output": False},
        api_base=os.getenv("VISUAL_PROMPT_LMM_API_BASE"),
        api_key=os.getenv("VISUAL_PROMPT_LMM_API_KEY")
    )

    # 3. 配置文本摘要模型（可选，用于non_visual_mode）
    text_summary_config = ModelConfig(
        model_name=os.getenv("RAG_LLM_API_NAME"),
        model_temperature=0,
        model_info={"vision": False, "function_calling": False, "json_output": False},
        api_base=os.getenv("RAG_LLM_API_BASE"),
        api_key=os.getenv("RAG_LLM_API_KEY")
    )

    # 4. 创建完整配置
    config = MinimalExecutorConfig(
        device=os.getenv("DEVICE_ID", "10.176.65.211:7421"),
        model_client=core_model_client,
        visual_prompt_model_config=visual_model_config,  # ⭐必须配置
        text_summarization_model_config=text_summary_config,
        non_visual_mode=False  # False=使用Set-of-Marks标记模式（推荐）
    )

    # 5. 创建执行器
    executor = MinimalFairyExecutor(
        device=config.device,
        model_client=config.model_client,
        config=config
    )

    # 6. 执行指令
    result = await executor.execute_instruction(
        instruction="预约12月12号才上线的新游戏",
        plan_context={
            "overall_plan": "找到12月12号的游戏",
            "current_sub_goal": "点击12-12"
        },
        execution_tips=""
    )

    # result = await executor.execute_instruction(
    #     instruction="购买一个麦辣鸡腿堡",
    #     plan_context={
    #         "overall_plan": "进入鸡腿汉堡的栏目",
    #         "current_sub_goal": "点击鸡腿汉堡/卷"
    #     },
    #     execution_tips=""
    # )

    print(f"执行成功: {result.success}")
    print(f"执行的动作: {result.actions_taken}")
    print(f"动作思考: {result.action_thought}")
    print(f"预期结果: {result.action_expectation}")
    if result.error:
        print(f"❌ 错误信息: {result.error}")

    return result

if __name__ == "__main__":
    asyncio.run(correct_usage())
