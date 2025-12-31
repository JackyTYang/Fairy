"""
探索计划管理器

负责生成初始计划和动态重新规划
"""

import json
import re
from typing import Optional

from Citlali.models.entity import ChatMessage
from Citlali.models.openai.client import OpenAIChatClient

from .config import ExplorerConfig
from .entities import (
    ExplorationTarget,
    ExplorationPlan,
    ExplorationStep,
    PerceptionOutput
)
from .tips_loader import get_tips_loader  # ⭐ 新增
from .logger import get_logger

logger = get_logger("ExplorationPlanner")


class ExplorationPlanner:
    """探索计划管理器

    使用LLM生成和更新探索计划

    Attributes:
        config: Explorer配置
        model_client: LLM客户端
        tips_loader: 应用特定提示加载器
    """

    def __init__(self, config: ExplorerConfig, session_dir=None):
        """
        Args:
            config: Explorer配置
            session_dir: 会话输出目录（用于保存prompt）
        """
        self.config = config
        self.session_dir = session_dir

        # 初始化LLM客户端
        self.model_client = OpenAIChatClient({
            "model": config.llm_model_name,
            "api_key": config.llm_api_key,
            "base_url": config.llm_api_base,
            "temperature": config.llm_temperature
        })

        # ⭐ 初始化Tips加载器
        self.tips_loader = get_tips_loader()

        logger.info(f"ExplorationPlanner初始化，模型: {config.llm_model_name}")

    async def create_initial_plan(
        self,
        target: ExplorationTarget,
        initial_perception: PerceptionOutput
    ) -> ExplorationPlan:
        """生成初始探索计划

        Args:
            target: 探索目标
            initial_perception: 初始屏幕感知结果

        Returns:
            ExplorationPlan: 初始计划
        """
        logger.info("开始生成初始探索计划...")

        # 读取压缩后的屏幕信息
        with open(initial_perception.compressed_txt_path, 'r', encoding='utf-8') as f:
            screen_text = f.read()

        # 加载带SoM标记的截图
        from PIL import Image
        marked_screenshot = Image.open(initial_perception.marked_screenshot_path)

        # 构建Prompt
        prompt = self._build_initial_plan_prompt(target, screen_text)

        # ⭐ 保存prompt到文件
        if self.session_dir:
            self._save_prompt_to_file(
                prompt_text=prompt,
                images=[initial_perception.marked_screenshot_path],
                system_message="你是一个应用功能探索助手，擅长分析应用界面并制定探索计划。你的探索结果将后续作为对该APP的知识，交给测试计划Agent进行app的测试用例生成，包括等价类划分和边界条件等。",
                output_path=self.session_dir / "initial_plan_prompt.txt"
            )

        # 调用LLM
        system_message = ChatMessage(
            content="你是一个应用功能探索助手，擅长分析应用界面并制定探索计划。你的探索结果将后续作为对该APP的知识，交给测试计划Agent进行app的测试用例生成，包括等价类划分和边界条件等。",
            type="SystemMessage"
        )
        user_message = ChatMessage(
            content=[prompt, marked_screenshot],
            type="UserMessage",
            source="user"
        )

        logger.debug("调用LLM生成初始计划...")
        response = await self.model_client.create([system_message, user_message])
        logger.debug(f"LLM响应长度: {len(response.content)} 字符")

        # 解析响应
        plan = self._parse_plan_response(response.content)

        logger.success(f"初始计划生成完成，共 {len(plan.steps)} 个步骤")

        return plan

    async def replan(
        self,
        target: ExplorationTarget,
        current_plan: ExplorationPlan,
        current_perception: PerceptionOutput,
        last_step: ExplorationStep,
        last_executor_result: dict,
        navigation_path: list,
        feature_tree=None,              # ⭐ 新增：完整功能树
        recent_state_sequence=None,     # ⭐ 新增：最近10个状态ID
        step_output_dir=None            # ⭐ 新增：step输出目录
    ) -> ExplorationPlan:
        """重新规划

        根据当前状态更新探索计划

        Args:
            target: 探索目标
            current_plan: 当前计划
            current_perception: 当前屏幕感知结果
            last_step: 上一步执行的步骤
            last_executor_result: 上一步Executor的执行结果
            navigation_path: 导航路径
            feature_tree: 完整功能树（用于提供历史状态信息）
            recent_state_sequence: 最近10个状态ID序列（用于循环检测）

        Returns:
            ExplorationPlan: 更新后的计划
        """
        logger.info(f"开始重新规划（上一步: {last_step.step_id}）...")

        # 读取当前屏幕信息（稳定截图，5秒）
        with open(current_perception.compressed_txt_path, 'r', encoding='utf-8') as f:
            screen_text = f.read()

        # 加载带SoM标记的截图（稳定截图，5秒）
        from PIL import Image
        marked_screenshot = Image.open(current_perception.marked_screenshot_path)

        # ⭐ 准备图像列表（可能包含双截图）
        images = []

        # 如果有立刻截图（0.2秒），加载它
        immediate_screen_text = None
        if (current_perception.immediate_screenshot_path and
            current_perception.immediate_screenshot_path is not None):
            immediate_screenshot = Image.open(current_perception.immediate_screenshot_path)
            images.append(immediate_screenshot)
            logger.info("检测到立刻截图（0.2秒），将一起传递给LLM")

            # 读取立刻截图的文本描述
            if (current_perception.immediate_compressed_txt_path and
                current_perception.immediate_compressed_txt_path is not None):
                with open(current_perception.immediate_compressed_txt_path, 'r', encoding='utf-8') as f:
                    immediate_screen_text = f.read()
        else:
            logger.info("单截图模式，只传递stable截图（5秒）")

        # 添加稳定截图（5秒）
        images.append(marked_screenshot)

        # 构建Replan Prompt
        prompt = self._build_replan_prompt(
            target,
            current_plan,
            screen_text,
            last_step,
            last_executor_result,
            navigation_path,
            immediate_screen_text=immediate_screen_text,  # 传递立刻截图的文本描述
            feature_tree=feature_tree,                    # ⭐ 新增
            recent_state_sequence=recent_state_sequence   # ⭐ 新增
        )

        # ⭐ 保存prompt到文件
        if step_output_dir:
            # 准备图片路径列表
            image_paths = []
            if (current_perception.immediate_screenshot_path and
                current_perception.immediate_screenshot_path is not None):
                image_paths.append(current_perception.immediate_screenshot_path)
            image_paths.append(current_perception.marked_screenshot_path)

            # 保存到step文件夹下
            from pathlib import Path
            output_path = Path(step_output_dir) / "replan_prompt.txt"
            self._save_prompt_to_file(
                prompt_text=prompt,
                images=image_paths,
                system_message="你是一个应用功能探索助手，擅长分析应用界面并制定探索计划。你的探索结果将后续作为对该APP的知识，交给测试计划Agent进行app的测试用例生成，包括等价类划分和边界条件等。",
                output_path=output_path
            )

        # 调用LLM
        system_message = ChatMessage(
            content="你是一个应用功能探索助手，擅长分析应用界面并制定探索计划。你的探索结果将后续作为对该APP的知识，交给测试计划Agent进行app的测试用例生成，包括等价类划分和边界条件等。",
            type="SystemMessage"
        )
        user_message = ChatMessage(
            content=[prompt] + images,  # ⭐ 传递所有截图（可能是1张或2张）
            type="UserMessage",
            source="user"
        )

        logger.debug("调用LLM重新规划...")
        response = await self.model_client.create([system_message, user_message])

        # 计算下一个步骤编号（从上一步的编号+1）
        # 从 last_step.step_id 中提取编号（例如 "step_3" -> 3）
        import re
        match = re.search(r'step_(\d+)', last_step.step_id)
        if match:
            next_step_num = int(match.group(1)) + 1
        else:
            # 兜底：基于已完成步骤数量计算
            next_step_num = len(current_plan.completed_steps) + 2

        # 解析响应（强制修正步骤ID）
        new_plan = self._parse_plan_response(
            response.content,
            is_replan=True,
            next_step_num=next_step_num
        )

        # 保留已完成的步骤
        new_plan.completed_steps = current_plan.completed_steps.copy()
        new_plan.completed_steps.append(last_step.step_id)

        logger.success(f"重新规划完成，共 {len(new_plan.steps)} 个步骤")

        return new_plan

    def get_next_step(self, plan: ExplorationPlan) -> Optional[ExplorationStep]:
        """从计划中获取下一步待执行的步骤

        Args:
            plan: 当前计划

        Returns:
            下一步要执行的步骤，如果没有则返回None
        """
        for step in plan.steps:
            if step.status == "pending":
                return step
        return None

    def _build_initial_plan_prompt(
        self,
        target: ExplorationTarget,
        screen_text: str
    ) -> str:
        """构建初始计划Prompt"""
        prompt = f"""你是一个应用功能探索助手。

## 探索目标
- 应用名称: {target.app_name}
- 应用包名: {target.app_package}
- 应用介绍: {target.app_description}
- 探索功能: {target.feature_to_explore}
- 当前状态: {target.starting_state}

## 当前屏幕信息
我们提供了当前屏幕的**带SoM标记的截图**和**文本描述**：
- **截图说明**：截图中使用红色方框标记了所有可点击元素，方框左上角的数字是该元素的编号
- **文本描述**：
```
{screen_text}
```

{self._get_app_specific_tips(target)}

## 探索执行指南 ⚠️ 重要

### 🎯 探索目标定位
探索的核心目的是**发现功能、理解页面结构、记录交互逻辑**，为后续测试用例设计提供信息基础。
- ✅ 要做：发现按钮、识别功能、理解流程、记录页面结构
- ❌ 不做：边界测试（如反复点击测试上限）、异常输入测试、压力测试
- 示例：发现"加减号按钮"即可，无需测试点击100次的行为
- 重点：知道"这里有什么功能"，而非"这个功能在各种情况下的表现"

### ⚠️ 安全操作准则
- 涉及金钱交易（支付/充值/购买）：仅探索到支付确认页面，**不要点击最终"确认支付"按钮**
- 避免产生真实订单、扣款或其他不可逆操作
- 看到金额和支付方式后即可返回

### 🔄 失败处理策略
- 如果某操作连续失败2-3次 → 放弃当前路径，记录失败原因
- 切换到其他未探索的功能或页面路径
- 不要在同一失败点反复重试

### 📱 多样化探索方式
- 合理使用滑动、长按等多种操作，不要只依赖点击
- 长列表/轮播图 → 先滑动浏览全部内容，再决定点击
- 避免过度点击导致频繁跳转 → 适当停留观察页面完整信息
"""
        # ⭐ 在任务前重复提醒禁止项
        forbidden_items = self.tips_loader.get_forbidden_items(
            app_package=target.app_package,
            app_name=target.app_name
        )

        if forbidden_items:
            prompt += f"""
## ⚠️⚠️⚠️ 严格禁止的操作（请牢记！）

在生成计划时，**绝对不要**生成以下操作：
"""
            for item in forbidden_items:
                prompt += f"- {item}\n"

            prompt += "\n"

        prompt += f"""
## 任务
根据你对该应用的世界知识、当前屏幕截图和文本描述，生成一个探索计划。

**要求**：
1. 计划应该将探索功能拆解为多个步骤，每个步骤对应一个具体的操作目标
2. 每个步骤都要有明确的指令(instruction)和子目标(sub_goal)
3. instruction 是传递给执行器的具体操作指令，如"点击XX按钮"、"向下滑动找到XX"
4. sub_goal 是该步骤要达到的目标状态，如"进入XX页面"、"找到XX元素"
5. 对于可能需要多次尝试的操作（如滑动查找），设置 enable_reflection=true 和适当的 max_iterations
6. 步骤数量不要超过 {self.config.max_plan_steps} 个
7. 步骤ID格式为 "step_1", "step_2", ...
8. **遵循上述探索执行指南，避免过度测试和危险操作**
9. ⚠️⚠️⚠️ **必须严格遵守上述"严格禁止的操作"！不要生成任何违反禁止规则的步骤！**

### ⚠️⚠️⚠️ 步骤粒度要求（非常重要！）
**每个步骤(step)必须只包含一个可独立验证的原子操作**：
- ✅ 正确示例：
  * step_1: "点击'人气热卖'分类，观察右侧商品列表变化"
  * step_2: "点击'大堡口福/单人餐'分类，观察右侧商品列表变化"
  * step_3: "点击'麦金卡专享'分类，观察右侧商品列表变化"
- ❌ 错误示例：
  * step_1: "依次点击'人气热卖''大堡口福/单人餐''麦金卡专享'三个分类，观察变化"  ← 包含了3个操作，无法验证中间状态！

**为什么要这样做？**
- 执行器在执行step时，只会在第一个操作后进行截图和反思
- 如果一个step包含多个操作，只能看到最终状态，无法验证中间过程
- 这会导致状态树丢失中间状态，测试规划无法复现操作路径

**拆分原则**：
- 如果instruction中包含"依次"、"然后"、"接着"、"再"等连接词 → 必须拆分成多个step
- 如果需要观察多次不同的页面变化 → 每次变化对应一个step
- 如果包含多个点击、滑动等交互操作 → 每个操作对应一个step
- 唯一例外：同一个操作的前置准备（如"先滑动到底部，再点击XX按钮"）可以合并，但观察验证必须独立

## 功能结构分析 ⭐ 重要
在制定探索计划时，请分析功能的层次结构：
1. **根功能**：{target.feature_to_explore}
2. **子功能**：根据应用的功能模块，将探索任务分解为多个子功能
   - 每个子功能应该是一个相对独立的功能模块
   - 例如：点餐功能可能包含"浏览菜单"、"选择套餐配品"、"加入购物车"、"结账支付"等子功能
   - 子功能数量建议2-5个，不要过细或过粗
3. 为每个子功能提供简短的描述

**注意**：⚠️ 初始计划中的功能结构是**基于世界知识的预测**，可能与实际不符。
- 这些feature作为探索的**参考框架**
- 在实际探索过程中，会根据真实页面内容动态调整
- 真正准确的feature应该是执行到具体页面后总结得出的

## 输出格式（JSON）
请输出一个JSON对象，格式如下：
```json
{{
  "plan_thought": "你的计划思考过程，包括对当前页面的分析和探索策略",
  "overall_plan": "整体计划的简洁描述，一句话概括",
  "feature_structure": {{
    "root_feature": "{target.feature_to_explore}",
    "sub_features": [
      {{
        "name": "子功能1名称",
        "description": "子功能1描述（1句话）"
      }},
      {{
        "name": "子功能2名称",
        "description": "子功能2描述（1句话）"
      }}
    ]
  }},
  "current_feature": {{
    "feature_path": ["{target.feature_to_explore}", "子功能1名称"],
    "status": "exploring"
  }},
  "steps": [
    {{
      "step_id": "step_1",
      "instruction": "具体操作指令",
      "sub_goal": "该步骤的目标",
      "enable_reflection": true,
      "max_iterations": 5
    }},
    {{
      "step_id": "step_2",
      "instruction": "具体操作指令",
      "sub_goal": "该步骤的目标",
      "enable_reflection": false,
      "max_iterations": 1
    }}
  ]
}}
```

请确保输出的JSON格式正确，可以被json.loads()解析。
"""
        return prompt

    def _build_replan_prompt(
        self,
        target: ExplorationTarget,
        current_plan: ExplorationPlan,
        screen_text: str,
        last_step: ExplorationStep,
        last_result: dict,
        navigation_path: list,
        immediate_screen_text: str = None,  # ⭐ 立刻截图的文本描述
        feature_tree = None,                 # ⭐ 新增：功能树
        recent_state_sequence = None         # ⭐ 新增：最近状态序列
    ) -> str:
        """构建重新规划Prompt - 优化版，结构清晰，加入CoT"""

        # 计算下一个步骤编号（从上一步的编号+1）
        match = re.search(r'step_(\d+)', last_step.step_id)
        if match:
            next_step_num = int(match.group(1)) + 1
        else:
            # 兜底：基于已完成步骤数量计算
            next_step_num = len(current_plan.completed_steps) + 2

        # ⭐ 获取应用特定提示（用于后续判断是否有禁止项）
        tips = self._get_app_specific_tips(target)
        forbidden_note = ""
        if tips and "⚠️" in tips:
            forbidden_note = "\n\n⚠️ **禁止项提醒**: 请严格遵守下方的应用特定禁止事项"

        # ========== 第1部分：执行上下文 ==========
        prompt = f"""# 应用功能探索 - 重新规划

## 📊 执行上下文

**探索目标**: {target.feature_to_explore}
**当前功能**: {' -> '.join(current_plan.current_feature.get('feature_path', [target.feature_to_explore]))}
**已完成步骤**: {len(current_plan.completed_steps)} 步

### 上一步执行结果
- **步骤**: {last_step.step_id} | {last_step.instruction}
- **结果**: {'✅ 成功' if last_result.get('success', False) else '❌ 失败'} ({last_result.get('execution_time', 0):.1f}秒，{last_result.get('iterations', 1)}次迭代)
- **目标**: {last_step.sub_goal}

---

## 🖼️ 当前屏幕
"""

        # ========== 第2部分：屏幕信息 ==========
        if immediate_screen_text:
            prompt += f"""
### 双截图模式
我们提供了两张截图：
1. **立刻截图（0.2秒）**: 捕获快速消失的toast/bubble
2. **稳定截图（5秒）**: 页面完全加载的状态

**立刻截图内容**:
```
{immediate_screen_text}
```

**稳定截图内容**:
```
{screen_text}
```

⚠️ 比较两张截图，关注只在立刻截图出现的提示/错误！
"""
        else:
            prompt += f"""
```
{screen_text}
```
"""

        # ========== 第3部分：探索指引 ==========
        prompt += f"""

---

## 📋 探索指引

### 核心目标
探索 = **发现功能** + **理解结构** + **记录交互**（为测试用例设计提供基础）

### 关键原则
1. ✅ **要做**: 发现按钮、识别功能、理解流程、记录页面结构
2. ❌ **不做**: 边界测试、异常输入、压力测试、重复操作
3. ⚠️ **安全**: 金钱交易→探索到确认页即停，失败2-3次→换路径
4. 📱 **多样**: 点击+滑动+长按组合，避免过度点击{forbidden_note}

{tips}

---

## 🎯 重新规划任务

### ⭐ 思考步骤（CoT - 必须完整包含在plan_thought中）

**第1步：屏幕分析**
- 当前页面是什么？（主页/列表/详情/弹窗...）
- 上一步达到预期了吗？
- 有哪些可交互元素？

**第2步：功能定位**
- 还在当前功能 `{' -> '.join(current_plan.current_feature.get('feature_path', [target.feature_to_explore]))}` 中吗？
- 如果不在→属于已有子功能/新功能/子子功能？

**第3步：探索策略**
- 当前功能完成度？
- 下一步：继续/切换/返回？

**第4步：步骤规划**
- 下一个原子操作是什么？
- 预期结果？
- 需要几次尝试？

---

## 📝 输出要求

### 步骤粒度 ⚠️ 极其重要
**每个step = 1个原子操作**

✅ 正确:
- step_{next_step_num}: "点击'新建文件夹'按钮"
- step_{next_step_num+1}: "输入'test'"

❌ 错误:
- step_{next_step_num}: "点击新建文件夹按钮，然后输入test"  ← 2个操作！

**原因**: 执行器只在第1个操作后截图，多操作丢失中间状态！

### JSON格式
```json
{{{{
  "plan_thought": "第1步：屏幕分析... 第2步：功能定位... 第3步：探索策略... 第4步：步骤规划...",
  "overall_plan": "简要整体计划（1-2句话）",
  "feature_update": {{{{"action": "none", "details": {{}}}}}},
  "current_feature": {{{{
    "feature_path": ["{target.feature_to_explore}", "子功能名"],
    "status": "exploring",
    "is_new_feature": false,
    "previous_feature_completed": false
  }}}},
  "steps": [
    {{{{
      "step_id": "step_{next_step_num}",
      "instruction": "具体操作（一个原子操作）",
      "sub_goal": "这步的目标",
      "enable_reflection": true,
      "max_iterations": 5
    }}}}
  ]
}}}}
```

**注意**:
- `plan_thought` 必须包含完整CoT（第1-4步）
- 步骤从 `step_{next_step_num}` 连续编号
- 虽然可生成多步，实际只执行第1步
- 最多 {self.config.max_plan_steps} 个步骤
"""

        # ⭐ 添加功能状态和历史信息
        prompt += self._build_feature_progress_section(current_plan, feature_tree, recent_state_sequence)

        # ⭐ 添加历史状态信息和循环检测
        if recent_state_sequence and feature_tree:
            prompt += self._build_history_section(
                recent_state_sequence,
                feature_tree,
                current_plan
            )

        return prompt

    def _parse_plan_response(
        self,
        response: str,
        is_replan: bool = False,
        next_step_num: int = 1
    ) -> ExplorationPlan:
        """解析LLM的计划响应

        Args:
            response: LLM响应文本
            is_replan: 是否是重新规划
            next_step_num: 下一个步骤编号（用于重新规划时强制修正步骤ID）

        Returns:
            ExplorationPlan对象
        """
        try:
            # 提取JSON（处理可能的markdown代码块）
            if "```json" in response:
                response = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL).group(1)
            elif "```" in response:
                response = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL).group(1)

            response_json = json.loads(response)

            # 构建步骤列表
            steps = []
            for i, step_data in enumerate(response_json.get('steps', [])):
                # 如果是重新规划，强制修正步骤ID为连续递增
                if is_replan:
                    corrected_step_id = f"step_{next_step_num + i}"
                else:
                    corrected_step_id = step_data['step_id']

                step = ExplorationStep(
                    step_id=corrected_step_id,
                    instruction=step_data['instruction'],
                    sub_goal=step_data['sub_goal'],
                    status="pending",
                    enable_reflection=step_data.get('enable_reflection', True),
                    max_iterations=step_data.get('max_iterations', 5)
                )
                steps.append(step)

            # 构建计划
            plan = ExplorationPlan(
                plan_thought=response_json.get('plan_thought', ''),
                overall_plan=response_json.get('overall_plan', ''),
                steps=steps,
                pending_steps=[step.step_id for step in steps],
                # ⭐ 新增：功能相关字段
                feature_structure=response_json.get('feature_structure', {}),
                current_feature=response_json.get('current_feature', {}),
                feature_update=response_json.get('feature_update', None)
            )

            return plan

        except Exception as e:
            logger.error(f"解析计划响应失败: {e}")
            logger.debug(f"响应内容: {response}")

            # 返回一个空计划
            return ExplorationPlan(
                plan_thought="解析失败",
                overall_plan="解析失败",
                steps=[],
                pending_steps=[]
            )

    def _get_app_specific_tips(self, target: ExplorationTarget) -> str:
        """获取应用特定的提示

        Args:
            target: 探索目标

        Returns:
            格式化的提示文本
        """
        tips = self.tips_loader.get_tips_for_app(
            app_package=target.app_package,
            app_name=target.app_name
        )

        if tips:
            logger.info(f"加载了应用特定提示: {target.app_name}")
            return tips
        else:
            return ""

    def _build_history_section(self, recent_states, feature_tree, current_plan) -> str:
        """构建历史状态信息section

        Args:
            recent_states: 最近的状态序列
            feature_tree: 功能树
            current_plan: 当前计划

        Returns:
            str: 格式化的历史状态信息
        """
        section = "\n\n" + "=" * 60 + "\n"
        section += "## 历史探索状态 ⚠️ 避免重复和循环\n"
        section += "=" * 60 + "\n\n"

        # 1. 最近访问的状态序列
        section += "### 最近访问的状态序列（最近10步）\n\n"
        section += self._format_recent_states(recent_states, feature_tree)
        section += "\n\n"

        # 2. 循环检测
        section += "### 循环检测 ⚠️\n\n"
        section += self._format_loop_detection(recent_states, feature_tree)
        section += "\n\n"

        # 3. 当前功能的探索历史
        section += "### 当前功能的探索历史\n\n"
        section += self._format_current_feature_history(current_plan.current_feature, feature_tree)
        section += "\n\n"

        # 4. 重要提醒
        section += """**重要提醒**：
- ⚠️ 如果连续3步以上停留在同一状态 → **可能陷入循环！**
- ⚠️ 如果当前指令与已完成步骤中的指令高度相似 → **可能重复操作！**

**应对策略**：
1. 检查是否已完成当前功能的探索目标
2. 如果已完成，使用Back或关闭按钮返回上一级
3. 如果未完成但陷入循环，尝试不同的操作方式（如滑动、长按）
4. 如果多次失败，放弃当前路径，切换到其他功能
"""

        return section

    def _format_recent_states(self, recent_states, feature_tree) -> str:
        """格式化最近访问的状态序列"""
        if not recent_states:
            return "无"

        lines = []
        for i, state_id in enumerate(recent_states[-10:]):
            step_num = len(recent_states) - 10 + i + 1
            if hasattr(feature_tree, 'states') and state_id in feature_tree.states:
                state = feature_tree.states[state_id]

                # ⭐ 从state_transitions动态计算访问次数
                # state_transitions格式: (from_state_id, to_state_id, step_id)
                visit_count = sum(1 for trans in feature_tree.state_transitions if trans[1] == state_id)

                lines.append(
                    f"{step_num}. {state.state_name} "
                    f"({state.activity_name}) - 已访问{visit_count}次"
                )
            else:
                lines.append(f"{step_num}. {state_id}")

        return "\n".join(lines)

    def _format_loop_detection(self, recent_states, feature_tree) -> str:
        """检测并格式化循环警告"""
        if not recent_states or len(recent_states) < 4:
            return "✅ 无异常"

        last_4 = recent_states[-4:]
        last_5 = recent_states[-5:] if len(recent_states) >= 5 else recent_states

        # 检测连续4步同一状态
        if len(set(last_4)) == 1:
            state_id = last_4[0]
            if hasattr(feature_tree, 'states') and state_id in feature_tree.states:
                state = feature_tree.states[state_id]

                # ⭐ 从state_transitions动态计算访问次数
                # state_transitions格式: (from_state_id, to_state_id, step_id)
                visit_count = sum(1 for trans in feature_tree.state_transitions if trans[1] == state_id)

                # ⭐ 从state_transitions提取在此状态执行的步骤
                steps_in_state = [trans[2] for trans in feature_tree.state_transitions if trans[1] == state_id]
                steps_str = ', '.join(steps_in_state[-5:]) if steps_in_state else 'N/A'

                return f"""
⚠️⚠️⚠️ **检测到循环！** ⚠️⚠️⚠️

- **当前状态**: {state.state_name} ({state_id})
- **停留时长**: 连续{len([s for s in last_5 if s == state_id])}步
- **已访问次数**: {visit_count}次
- **在此状态执行的步骤**: {steps_str}

**强烈建议**：
1. 如果弹窗或子功能已充分探索 → 点击Back/关闭按钮返回
2. 如果操作反复失败 → 放弃当前路径，切换到其他功能
3. **不要再继续在同一状态重复相同操作！**
"""
            else:
                return f"""
⚠️⚠️⚠️ **检测到循环！** ⚠️⚠️⚠️

- **当前状态**: {state_id}
- **停留时长**: 连续{len([s for s in last_5 if s == state_id])}步

**强烈建议**: 点击Back/关闭按钮返回，或切换到其他功能
"""

        # 检测频繁往返（A→B→A→B）
        if len(recent_states) >= 4:
            if recent_states[-1] == recent_states[-3] and recent_states[-2] == recent_states[-4]:
                return f"""
⚠️ **检测到往返循环！**

- 过去4步在 {recent_states[-1]} 和 {recent_states[-2]} 之间反复跳转
- 建议：停止当前路径，尝试新的探索方向
"""

        return "✅ 无异常"

    def _format_current_feature_history(self, current_feature, feature_tree) -> str:
        """格式化当前功能的探索历史"""
        if not current_feature:
            return "无"

        feature_path = current_feature.get('feature_path', [])

        # 统计功能树中的状态
        total_states = len(feature_tree.states) if hasattr(feature_tree, 'states') else 0
        total_transitions = len(feature_tree.state_transitions) if hasattr(feature_tree, 'state_transitions') else 0

        return f"""
- 已探索状态数: {total_states}
- 状态转移次数: {total_transitions}
- 当前功能路径: {' -> '.join(feature_path)}
"""

    def _build_feature_progress_section(self, current_plan, feature_tree, recent_state_sequence) -> str:
        """构建功能探索状态提示

        列出已完成和正在探索的功能，避免LLM重复进入已完成的功能

        Args:
            current_plan: 当前计划
            feature_tree: 功能树
            recent_state_sequence: 最近的状态序列

        Returns:
            str: 格式化的功能状态提示
        """
        if not feature_tree or not hasattr(feature_tree, 'features'):
            return ""

        section = "\n" + "=" * 60 + "\n"
        section += "## ⚠️ 功能探索状态 - 避免重复探索已完成的功能 ⚠️\n"
        section += "=" * 60 + "\n\n"

        # 1. 统计功能探索状态
        exploring_features = []
        completed_features = []

        for feature_id, feature_node in feature_tree.features.items():
            if feature_id == "root":
                continue

            feature_info = {
                'name': feature_node.feature_name,
                'states': len(feature_node.states),
                'description': feature_node.feature_description,
                'completed_at': feature_node.completed_at
            }

            if feature_node.status == "completed":
                completed_features.append(feature_info)
            else:
                exploring_features.append(feature_info)

        # 2. 列出已完成的功能
        section += "### ✅ 已完成探索的功能（请勿重复进入）\n"
        if completed_features:
            for feat in completed_features:
                section += f"- ✅ **{feat['name']}**：已完成（探索了{feat['states']}个状态，完成于{feat['completed_at']}）\n"
                section += f"  └─ {feat['description']}\n"
            section += f"\n**重要约束**：\n"
            section += f"- ❌ **禁止**：生成进入上述已完成功能的步骤\n"
            section += f"- ❌ **禁止**：点击上述功能相关的入口按钮/菜单\n"
            section += f"- 示例：如果「商品规格选择弹层」已完成，不要再生成「点击XX商品的选规格按钮」\n\n"
        else:
            section += "- 无\n\n"

        # 3. 列出正在探索的功能
        section += "### 🔄 正在探索的功能\n"
        if exploring_features:
            for feat in exploring_features:
                section += f"- 🔄 **{feat['name']}**：正在探索（已探索{feat['states']}个状态）\n"
                section += f"  └─ {feat['description']}\n"
        else:
            section += "- 无\n"

        section += "\n"

        # 4. 检测页面往返循环
        if recent_state_sequence and len(recent_state_sequence) >= 3:
            recent_activities = []
            for state_id in recent_state_sequence[-3:]:
                if state_id in feature_tree.states:
                    state = feature_tree.states[state_id]
                    recent_activities.append(state.activity_name)

            # 检测往返模式（A→B→A）
            if len(recent_activities) >= 3:
                if recent_activities[-1] == recent_activities[-3] and recent_activities[-1] != recent_activities[-2]:
                    activity_a = recent_activities[-1]
                    activity_b = recent_activities[-2]

                    section += "### ⚠️⚠️⚠️ 检测到页面往返循环 ⚠️⚠️⚠️\n\n"
                    section += f"**循环模式**：\n"
                    section += f"- 最近3步在两个页面之间往返：`{activity_a}` → `{activity_b}` → `{activity_a}`\n"
                    section += f"- 这通常表示：反复进入和退出同一个弹层/详情页\n\n"

                    section += f"**推进建议**：\n"
                    section += f"1. **不要再进入刚才退出的页面**（`{activity_b}`）\n"
                    section += f"2. **推进到新功能**：\n"
                    section += f"   - 如果当前在列表页：点击底部的「去结算」「购物车」等主要功能入口\n"
                    section += f"   - 或点击顶部的「门店设置」「优惠券」等未探索功能\n"
                    section += f"3. **禁止的操作**：\n"
                    section += f"   - ❌ 再次点击刚才探索过的商品/详情页入口\n"
                    section += f"   - ❌ 重复执行之前的操作\n\n"

        return section

    def _save_prompt_to_file(
        self,
        prompt_text: str,
        images: list,
        system_message: str,
        output_path
    ):
        """保存prompt到文件

        Args:
            prompt_text: 用户消息的文本部分
            images: 图片路径列表
            system_message: 系统消息文本
            output_path: 输出文件路径（Path对象）
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("SYSTEM MESSAGE\n")
                f.write("=" * 80 + "\n")
                f.write(system_message + "\n\n")

                f.write("=" * 80 + "\n")
                f.write("USER MESSAGE - TEXT\n")
                f.write("=" * 80 + "\n")
                f.write(prompt_text + "\n\n")

                f.write("=" * 80 + "\n")
                f.write("USER MESSAGE - IMAGES\n")
                f.write("=" * 80 + "\n")
                for i, img_path in enumerate(images, 1):
                    f.write(f"Image {i}: {img_path}\n")
                f.write("\n")

            logger.info(f"Prompt已保存到: {output_path}")
        except Exception as e:
            logger.error(f"保存prompt失败: {e}")
