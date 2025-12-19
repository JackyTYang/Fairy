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
from .logger import get_logger

logger = get_logger("ExplorationPlanner")


class ExplorationPlanner:
    """探索计划管理器

    使用LLM生成和更新探索计划

    Attributes:
        config: Explorer配置
        model_client: LLM客户端
    """

    def __init__(self, config: ExplorerConfig):
        """
        Args:
            config: Explorer配置
        """
        self.config = config

        # 初始化LLM客户端
        self.model_client = OpenAIChatClient({
            "model": config.llm_model_name,
            "api_key": config.llm_api_key,
            "base_url": config.llm_api_base,
            "temperature": config.llm_temperature
        })

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

        # 调用LLM
        system_message = ChatMessage(
            content="你是一个应用功能探索助手，擅长分析应用界面并制定探索计划。",
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
        navigation_path: list
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
        if current_perception.immediate_screenshot_path:
            immediate_screenshot = Image.open(current_perception.immediate_screenshot_path)
            images.append(immediate_screenshot)
            logger.info("检测到立刻截图（0.2秒），将一起传递给LLM")

            # 读取立刻截图的文本描述
            if current_perception.immediate_compressed_txt_path:
                with open(current_perception.immediate_compressed_txt_path, 'r', encoding='utf-8') as f:
                    immediate_screen_text = f.read()
            else:
                immediate_screen_text = None
        else:
            immediate_screen_text = None

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
            immediate_screen_text=immediate_screen_text  # 传递立刻截图的文本描述
        )

        # 调用LLM
        system_message = ChatMessage(
            content="你是一个应用功能探索助手，擅长根据执行结果动态调整探索计划。",
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

## 输出格式（JSON）
请输出一个JSON对象，格式如下：
```json
{{
  "plan_thought": "你的计划思考过程，包括对当前页面的分析和探索策略",
  "overall_plan": "整体计划的简洁描述，一句话概括",
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
        immediate_screen_text: str = None  # ⭐ 新增：立刻截图的文本描述
    ) -> str:
        """构建重新规划Prompt"""
        # 计算下一个步骤编号（从上一步的编号+1）
        import re
        match = re.search(r'step_(\d+)', last_step.step_id)
        if match:
            next_step_num = int(match.group(1)) + 1
        else:
            # 兜底：基于已完成步骤数量计算
            next_step_num = len(current_plan.completed_steps) + 2

        # 构建已完成步骤的摘要
        completed_summary = "\n".join([
            f"- {step_id}: {step.instruction}"
            for step_id in current_plan.completed_steps
            for step in current_plan.steps
            if step.step_id == step_id
        ])

        # ⭐ 构建截图说明（根据是否有双截图）
        if immediate_screen_text:
            screenshot_description = """我们提供了执行后的**两张带SoM标记的截图**和**文本描述**：
1. **立刻截图**（执行后0.2秒）：可能包含短暂的toast/bubble提示、错误消息或加载状态
2. **稳定截图**（执行后5秒）：页面完全加载后的稳定状态
- **截图说明**：截图中使用红色方框标记了所有可点击元素，方框左上角的数字是该元素的编号"""
        else:
            screenshot_description = """我们提供了执行后的**带SoM标记的截图**和**文本描述**：
- **截图说明**：截图中使用红色方框标记了所有可点击元素，方框左上角的数字是该元素的编号"""

        prompt = f"""你是一个应用功能探索助手。

## 当前探索状态
- 探索目标: {target.feature_to_explore}
- 当前导航路径: {' -> '.join(navigation_path)}
- 已完成步骤数: {len(current_plan.completed_steps)}

## 已完成的步骤
{completed_summary if completed_summary else "无"}

## 上一步执行结果
- 步骤ID: {last_step.step_id}
- 指令: {last_step.instruction}
- 子目标: {last_step.sub_goal}
- 执行成功: {last_result.get('success', False)}
- 迭代次数: {last_result.get('iterations', 1)}
- 执行时间: {last_result.get('execution_time', 0):.2f}秒

## 当前屏幕信息
{screenshot_description}
"""

        # ⭐ 如果有立刻截图，添加其文本描述
        if immediate_screen_text:
            prompt += f"""
### 1. 立刻截图（0.2秒）文本描述
**重要**：这是执行后0.2秒立刻截图的内容，可能包含快速消失的toast/bubble提示！
```
{immediate_screen_text}
```

### 2. 稳定截图（5秒）文本描述
这是执行后5秒的稳定页面：
```
{screen_text}
```

**分析提示**：请特别关注立刻截图中是否有任何toast/bubble/错误提示只在立刻截图中出现而不在稳定截图中，这些是应用对操作的即时反馈，对判断执行结果非常重要！
"""
        else:
            prompt += f"""
- **文本描述**：
```
{screen_text}
```
"""

        prompt += f"""

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

## 任务
根据当前状态、屏幕截图和文本描述，**重新规划后续的探索步骤**（从第 {next_step_num} 步开始）：

**要求**：
1. 分析当前屏幕是否到达了新页面
2. 判断探索目标的完成程度
3. 生成后续的探索步骤（从 step_{next_step_num} 开始编号）
4. **重要**：虽然你生成了多个步骤，但实际上只会执行第一个步骤，执行后会再次重新规划
5. 因此，请重点关注**当前页面**可以执行的下一步操作
6. 步骤数量不要超过 {self.config.max_plan_steps} 个
7. **必须从 step_{next_step_num} 开始连续编号**（step_{next_step_num}, step_{next_step_num+1}, ...）
8. **遵循上述探索执行指南，避免过度测试和危险操作**

## 输出格式（JSON）
请输出一个JSON对象，格式如下：
```json
{{
  "plan_thought": "你的重新规划思考，包括对当前页面的分析和下一步策略",
  "overall_plan": "更新后的整体计划描述",
  "steps": [
    {{
      "step_id": "step_{next_step_num}",
      "instruction": "具体操作指令",
      "sub_goal": "该步骤的目标",
      "enable_reflection": true/false,
      "max_iterations": N
    }},
    {{
      "step_id": "step_{next_step_num + 1}",
      "instruction": "具体操作指令",
      "sub_goal": "该步骤的目标",
      "enable_reflection": true/false,
      "max_iterations": N
    }}
  ]
}}
```

请确保输出的JSON格式正确，可以被json.loads()解析。
"""
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
                pending_steps=[step.step_id for step in steps]
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
