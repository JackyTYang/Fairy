# Explorer Planner & Replanner 输入分析

**分析时间**: 2025-12-23
**目标**: 理解Planner和Replanner的输入，为解决循环探索问题提供依据

---

## 一、Planner & Replanner 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                       FairyExplorer                         │
│                     (explorer.py)                           │
│                                                             │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │  初始计划     │      │   重新规划    │                    │
│  │ Initial Plan │      │    Replan    │                    │
│  └──────┬───────┘      └──────┬───────┘                    │
│         │                     │                             │
│         v                     v                             │
│  ┌─────────────────────────────────────────┐               │
│  │     ExplorationPlanner                  │               │
│  │         (planner.py)                    │               │
│  │                                         │               │
│  │  • create_initial_plan()                │               │
│  │  • replan()                             │               │
│  │  • _build_initial_plan_prompt()         │               │
│  │  • _build_replan_prompt()               │               │
│  └─────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、Initial Planner 输入分析

### 2.1 函数签名

```python
async def create_initial_plan(
    self,
    target: ExplorationTarget,              # ⭐ 探索目标
    initial_perception: PerceptionOutput    # ⭐ 初始屏幕感知
) -> ExplorationPlan:
```

### 2.2 输入详解

#### 输入1: `ExplorationTarget`

**来源**: `explorer.explore()` 参数

**包含字段**:
```python
class ExplorationTarget:
    app_name: str                # 应用名称，如 "麦当劳"
    app_package: str             # 应用包名，如 "com.mcdonalds.gma.cn"
    app_description: str         # 应用介绍
    feature_to_explore: str      # 探索的功能，如 "麦乐送点餐功能"
    starting_state: str          # 起始状态描述，如 "麦当劳首页"
```

**示例**:
```json
{
  "app_name": "麦当劳",
  "app_package": "com.mcdonalds.gma.cn",
  "app_description": "快餐点餐应用",
  "feature_to_explore": "麦乐送点餐功能",
  "starting_state": "麦当劳首页"
}
```

#### 输入2: `PerceptionOutput`

**来源**: `self.perceptor.capture_and_perceive()`

**包含字段**:
```python
class PerceptionOutput:
    compressed_txt_path: Path          # 压缩后的UI文本描述（AccessibilityTree）
    marked_screenshot_path: Path       # 带SoM标记的截图（红框+数字）
    immediate_screenshot_path: Path    # 立刻截图（0.2秒，可能为None）
    immediate_compressed_txt_path: Path  # 立刻截图的文本描述（可能为None）
    # ... 其他字段
```

**示例文件路径**:
```
/output/20251223_145104/perceptor_temp/20251223_145207/
  ├── compressed.txt             # UI结构文本
  ├── screenshot_marked.jpeg     # 带SoM标记的截图
  ├── som_mapping.json          # SoM Mark → 坐标映射
  └── ui_dump.xml               # 原始AccessibilityTree
```

### 2.3 传递给LLM的信息

**Prompt构建** (`_build_initial_plan_prompt()`):

```python
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
{screen_text}  # 从compressed_txt_path读取
```

{self._get_app_specific_tips(target)}  # 应用特定提示

## 探索执行指南 ⚠️ 重要
### 🎯 探索目标定位
... (避免过度测试、安全操作准则、失败处理策略)

## 功能结构分析 ⭐ 重要
在制定探索计划时，请分析功能的层次结构：
1. **根功能**：{target.feature_to_explore}
2. **子功能**：根据应用的功能模块，将探索任务分解为多个子功能

## 输出格式（JSON）
...
"""
```

**传递的图像**:
```python
user_message = ChatMessage(
    content=[prompt, marked_screenshot],  # ⭐ 文本+图像
    type="UserMessage"
)
```

### 2.4 Initial Planner **缺少**的信息

❌ 无历史信息（这是初始计划，合理）

---

## 三、Replanner 输入分析

### 3.1 函数签名

```python
async def replan(
    self,
    target: ExplorationTarget,              # ⭐ 探索目标（同上）
    current_plan: ExplorationPlan,          # ⭐ 当前计划
    current_perception: PerceptionOutput,   # ⭐ 当前屏幕感知（执行后）
    last_step: ExplorationStep,             # ⭐ 上一步执行的步骤
    last_executor_result: dict,             # ⭐ 上一步Executor结果
    navigation_path: list                   # ⭐ 导航路径
) -> ExplorationPlan:
```

### 3.2 输入详解

#### 输入1-2: `target` & `current_perception`
与Initial Planner相同，不再赘述。

#### 输入3: `ExplorationPlan` (current_plan)

**来源**: 上一次规划的结果

**包含字段**:
```python
class ExplorationPlan:
    plan_thought: str                      # LLM的规划思考
    overall_plan: str                      # 整体计划描述
    steps: List[ExplorationStep]           # 步骤列表
    completed_steps: List[str]             # 已完成的步骤ID列表
    pending_steps: List[str]               # 待执行的步骤ID列表

    # ⭐ 功能相关字段（新增）
    feature_structure: dict                # 功能结构
    current_feature: dict                  # 当前正在探索的功能
    feature_update: dict                   # 功能结构更新
```

**示例**:
```json
{
  "overall_plan": "从首页进入麦乐送，浏览菜单，选择商品加入购物车",
  "completed_steps": ["step_1", "step_2"],
  "pending_steps": ["step_3", "step_4"],
  "feature_structure": {
    "root_feature": "麦乐送点餐功能",
    "sub_features": [
      {"name": "菜单浏览", "description": "浏览商品分类和商品列表"},
      {"name": "商品选择", "description": "选择商品规格和数量"}
    ]
  },
  "current_feature": {
    "feature_path": ["麦乐送点餐功能", "菜单浏览"],
    "status": "exploring"
  }
}
```

#### 输入4: `ExplorationStep` (last_step)

**来源**: 刚刚执行完的步骤

**包含字段**:
```python
class ExplorationStep:
    step_id: str                 # 步骤ID，如 "step_3"
    instruction: str             # 操作指令，如 "点击Mark 6"
    sub_goal: str                # 子目标，如 "进入商品详情页"
    status: str                  # "pending" | "executing" | "completed" | "failed"
    enable_reflection: bool      # 是否启用反思
    max_iterations: int          # 最大迭代次数
```

**示例**:
```json
{
  "step_id": "step_3",
  "instruction": "在左侧分类列表中，点击非高亮分类",
  "sub_goal": "切换分类，观察右侧商品列表变化",
  "status": "completed",
  "enable_reflection": true,
  "max_iterations": 3
}
```

#### 输入5: `dict` (last_executor_result)

**来源**: `executor_result.to_dict()`

**包含字段**:
```python
{
    "success": true/false,                 # 执行是否成功
    "iterations": 2,                       # 实际迭代次数
    "execution_time": 5.23,               # 执行时间（秒）
    "actions": [                          # 执行的动作列表
        {
            "name": "Tap",
            "arguments": {"x": 100, "y": 1918}
        }
    ],
    "screen_before": {...},               # 执行前屏幕信息（ScreenInfo）
    "screen_after": {...},                # 执行后屏幕信息（ScreenInfo）
    "progress_info": {                    # 进度信息
        "action_result": "A",  # A=新页面, B=页面变化, C=无变化
        ...
    },
    "reflection_log": [...]               # 反思日志
}
```

**示例**:
```json
{
  "success": true,
  "iterations": 1,
  "execution_time": 3.45,
  "actions": [
    {
      "name": "Tap",
      "arguments": {"x": 100, "y": 1918}
    }
  ],
  "progress_info": {
    "action_result": "A",
    "description": "页面从ProductMdsListActivity跳转到CouponListV2Activity"
  }
}
```

#### 输入6: `list` (navigation_path)

**来源**: `self.state_tracker.get_current_path()`

**格式**: 字符串列表，记录导航路径

**示例**:
```python
[
    "首页",
    "确认优惠券详情页中\"订阅使用提醒\"按钮的基本交互反馈形态",
    "确认在系统日历权限弹窗中选择\"允许\"后的影响",
    "确认在授权并已订阅成功状态下，点击\"已订阅提醒\"按钮的交互逻辑"
]
```

### 3.3 传递给LLM的信息

**Prompt构建** (`_build_replan_prompt()`):

```python
prompt = f"""你是一个应用功能探索助手。

## 当前探索状态
- 探索目标: {target.feature_to_explore}
- 当前导航路径: {' -> '.join(navigation_path)}  # ⭐ 提供了导航路径
- 已完成步骤数: {len(current_plan.completed_steps)}

## 已完成的步骤
{completed_summary}  # ⭐ 列出所有已完成步骤的指令

## 上一步执行结果
- 步骤ID: {last_step.step_id}
- 指令: {last_step.instruction}
- 子目标: {last_step.sub_goal}
- 执行成功: {last_result.get('success')}
- 迭代次数: {last_result.get('iterations')}
- 执行时间: {last_result.get('execution_time')}秒

## 当前屏幕信息
{screenshot_description}  # 说明截图类型（单张或双张）

{screen_text}  # 稳定截图（5秒）的文本描述

{immediate_screen_text}  # ⭐ 如果有立刻截图（0.2秒），提供其文本

## 当前功能探索状态
- 当前正在探索的功能路径: {' -> '.join(current_plan.current_feature.get('feature_path'))}
- 已发现的子功能: {', '.join([f['name'] for f in current_plan.feature_structure.get('sub_features')])}

## 任务
根据当前状态、屏幕截图和文本描述，完成以下任务：

### 1. 功能状态判断 ⭐ 重要
请根据当前页面的实际内容判断：
**A. 是否还在当前功能中？**
**B. 如果不在当前功能，当前属于：**
   - 【情况1】初始计划中已有的子功能
   - 【情况2】新发现的子功能
   - 【情况3】当前子功能的子子功能
**C. 是否需要更新功能结构？**

### 2. 重新规划后续步骤
...
"""
```

**传递的图像**:
```python
user_message = ChatMessage(
    content=[prompt] + images,  # ⭐ 文本 + 1-2张图像
    type="UserMessage"
)

# images可能包含：
# 1. immediate_screenshot（0.2秒）+ marked_screenshot（5秒）
# 2. 或只有marked_screenshot（5秒）
```

### 3.4 Replanner **缺少**的关键信息 ⚠️

根据 `EXPLORATION_LOOP_ANALYSIS.md` 的分析，Replanner缺少以下关键信息：

#### ❌ 1. 历史状态序列

**当前**: 只有 `navigation_path`（路径名称列表）
```python
navigation_path = ["首页", "优惠券页", "权限弹窗"]
```

**缺少**: 状态ID序列和重复检测
```python
recent_state_sequence = [
    "state_productmdslist_a4f2f6f0",
    "state_productmdslist_e960fb61",  # 第1次
    "state_productmdslist_e960fb61",  # 第2次
    "state_productmdslist_e960fb61",  # 第3次 ⚠️ 循环!
    "state_productmdslist_e960fb61"   # 第4次
]
```

**影响**: LLM不知道自己在同一状态停留了多久，无法察觉循环。

#### ❌ 2. 完整的功能树信息

**当前**: 只有 `current_plan.feature_structure`（初始计划的功能结构）
```python
feature_structure = {
    "root_feature": "麦乐送点餐功能",
    "sub_features": [...]  # 只有名称和描述
}
```

**缺少**: 功能树的状态信息（`FeatureTree` 对象）
```python
feature_tree = {
    "states": {
        "state_e960fb61": {
            "state_name": "配送时间弹窗",
            "activity_name": "ProductMdsListActivity",
            "visited_count": 5,  # ⚠️ 已访问5次！
            "reachable_states": ["state_a4f2f6f0"],
            "steps_in_this_state": ["step_3", "step_4", "step_5", "step_6", "step_7"]
        }
    },
    "state_transitions": [
        {"step": "step_3", "from": "state_a4f2f6f0", "to": "state_e960fb61"},
        {"step": "step_4", "from": "state_e960fb61", "to": "state_e960fb61"},  # 自环
        {"step": "step_5", "from": "state_e960fb61", "to": "state_e960fb61"},  # 自环
        ...
    ]
}
```

**影响**: LLM不知道当前状态的访问历史，无法判断是否过度探索。

#### ❌ 3. 循环检测提示

**当前**: Prompt中没有循环警告

**缺少**:
```python
## 循环检测 ⚠️

**当前状态**: state_productmdslist_e960fb61
**过去5步的状态**: [e960fb61, e960fb61, e960fb61, e960fb61, e960fb61]

**⚠️ 警告**: 连续5步都在同一状态，可能陷入循环！

**应对策略**：
1. 检查是否已完成当前功能的探索目标
2. 如果已完成，使用Back或关闭按钮返回
3. 如果未完成但陷入循环，尝试不同的操作方式
4. 如果多次失败，放弃当前路径，切换到其他功能
```

**影响**: LLM缺少明确的循环感知和退出引导。

#### ❌ 4. 功能完成度判断提示

**当前**: Prompt中有功能状态判断，但没有明确的完成度评估

**缺少**:
```python
## 功能完成度评估 ⭐ 必须回答

对于当前功能：{' -> '.join(current_feature_path)}

请回答以下问题：
1. **核心元素是否已识别？**
2. **核心交互是否已测试？**
3. **页面状态是否已遍历？**
4. **是否需要继续深入？**

**判断标准**：
- ✅ 核心元素已识别 + 核心交互已测试 + 无子页面 → 功能完成，应返回
- ⚠️ 仅在同一页面反复切换选项 → 可能过度探索，应返回
- ❌ 有子页面未进入 → 功能未完成，应深入探索
```

**影响**: LLM不知道何时应该结束当前功能并返回。

---

## 四、循环探索问题的根本原因

根据输入分析和 `EXPLORATION_LOOP_ANALYSIS.md`，循环探索的根本原因是：

### 4.1 **信息断层**

```
┌─────────────────────────────────────────────────────────┐
│          FeatureTreeBuilder (功能树)                    │
│                                                         │
│  ✓ 记录了所有状态 (states)                              │
│  ✓ 记录了状态转移 (state_transitions)                   │
│  ✓ 记录了状态访问历史 (visited_count)                   │
│                                                         │
│          ❌ 但没有传递给 Planner！                       │
└─────────────────────────────────────────────────────────┘
                         │
                         │ 缺失的传递
                         ↓
┌─────────────────────────────────────────────────────────┐
│         ExplorationPlanner (规划器)                     │
│                                                         │
│  ❌ 不知道状态访问历史                                   │
│  ❌ 不知道是否在循环                                     │
│  ❌ 不知道何时应该退出                                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.2 **具体表现**

以问题案例（20251220_172306）为例：

| 步骤 | 状态ID | Planner看到的 | Planner **没看到**的 |
|------|--------|--------------|-------------------|
| Step 3 | state_e960fb61 | ✓ 上一步执行成功<br>✓ 当前屏幕内容 | ❌ 这是第1次访问此状态 |
| Step 4 | state_e960fb61 | ✓ 上一步执行成功<br>✓ 当前屏幕内容 | ❌ 这是第2次访问此状态 |
| Step 5 | state_e960fb61 | ✓ 上一步执行失败<br>✓ 当前屏幕内容 | ❌ **这是第3次访问此状态**<br>❌ **连续3步无进展** |
| Step 6 | state_e960fb61 | ✓ 上一步执行成功<br>✓ 当前屏幕内容 | ❌ **这是第4次访问此状态**<br>❌ **已陷入循环** |
| Step 7 | state_e960fb61 | ✓ 上一步执行成功<br>✓ 当前屏幕内容 | ❌ **这是第5次访问此状态**<br>❌ **应该强制退出** |

**结果**: Planner在每一步都认为"上一步成功了，继续探索吧"，完全没有意识到自己在原地打转。

---

## 五、解决方案设计

### 5.1 方案概览

根据 `EXPLORATION_LOOP_ANALYSIS.md` 的建议，我们需要：

| 方案 | 实施难度 | 效果 | 推荐度 |
|------|---------|------|--------|
| **方案1**: 增强Planner上下文感知 | 中等 | 根本解决 | ⭐⭐⭐⭐⭐ |
| **方案2**: 改进State识别粒度 | 低 | 部分缓解 | ⭐⭐⭐ |
| **方案3**: 功能完成度判断 | 中等 | 智能终止 | ⭐⭐⭐⭐ |
| **方案4**: 循环检测（硬编码） | 低 | 快速见效 | ⭐⭐⭐⭐ |

### 5.2 方案1详细设计：增强Planner上下文感知 ⭐ 推荐

#### Step 1: 修改 `planner.replan()` 函数签名

```python
async def replan(
    self,
    target: ExplorationTarget,
    current_plan: ExplorationPlan,
    current_perception: PerceptionOutput,
    last_step: ExplorationStep,
    last_executor_result: dict,
    navigation_path: list,
    feature_tree: FeatureTree,              # ⭐ 新增：完整功能树
    recent_state_sequence: List[str]        # ⭐ 新增：最近10个状态ID
) -> ExplorationPlan:
```

#### Step 2: 修改 `explorer.py` 的调用

```python
# explorer.py:297
current_plan = await self.planner.replan(
    target,
    current_plan,
    replan_perception,
    next_step,
    executor_result_dict,
    self.state_tracker.get_current_path(),
    # ⭐ 新增参数
    feature_tree=self.feature_tree_builder.tree,  # 完整功能树
    recent_state_sequence=self._get_recent_state_sequence()  # 最近状态
)
```

#### Step 3: 在 `explorer.py` 中添加辅助方法

```python
def _get_recent_state_sequence(self) -> List[str]:
    """获取最近10个状态ID序列

    Returns:
        List[str]: 状态ID列表，如 ["state_xxx", "state_yyy", ...]
    """
    # 从feature_tree的state_transitions中提取
    if not self.feature_tree_builder:
        return []

    transitions = self.feature_tree_builder.tree.state_transitions
    recent_transitions = transitions[-10:] if len(transitions) >= 10 else transitions

    return [trans['to'] for trans in recent_transitions]
```

#### Step 4: 增强 `_build_replan_prompt()`

```python
def _build_replan_prompt(
    self,
    target: ExplorationTarget,
    current_plan: ExplorationPlan,
    screen_text: str,
    last_step: ExplorationStep,
    last_result: dict,
    navigation_path: list,
    feature_tree: FeatureTree = None,           # ⭐ 新增
    recent_state_sequence: List[str] = None,    # ⭐ 新增
    immediate_screen_text: str = None
) -> str:
    # ... 原有Prompt内容 ...

    # ⭐ 新增：历史状态信息
    if recent_state_sequence and feature_tree:
        prompt += f"""

## 历史探索状态 ⚠️ 避免重复

### 最近访问的状态序列（最近10步）
{self._format_recent_states(recent_state_sequence, feature_tree)}

### 循环检测 ⚠️
{self._format_loop_detection(recent_state_sequence, feature_tree)}

### 当前功能的探索历史
{self._format_current_feature_history(current_plan.current_feature, feature_tree)}

**重要提醒**：
- 如果连续3步以上停留在同一状态 → **可能陷入循环！**
- 如果当前指令与已完成步骤中的指令高度相似 → **可能重复操作！**
- 应对策略：
  1. 检查是否已完成当前功能的探索目标
  2. 如果已完成，使用Back或关闭按钮返回
  3. 如果未完成但陷入循环，尝试不同的操作方式（如滑动、长按）
  4. 如果多次失败，放弃当前路径，切换到其他功能
"""

    return prompt
```

#### Step 5: 实现格式化辅助方法

```python
def _format_recent_states(self, recent_states: List[str], feature_tree: FeatureTree) -> str:
    """格式化最近访问的状态序列"""
    if not recent_states:
        return "无"

    lines = []
    for i, state_id in enumerate(recent_states[-10:]):
        if state_id in feature_tree.states:
            state = feature_tree.states[state_id]
            lines.append(
                f"{len(recent_states) - 10 + i + 1}. {state.state_name} "
                f"({state.activity_name}) - 已访问{state.visited_count}次"
            )
        else:
            lines.append(f"{len(recent_states) - 10 + i + 1}. {state_id}")

    return "\n".join(lines)

def _format_loop_detection(self, recent_states: List[str], feature_tree: FeatureTree) -> str:
    """检测并格式化循环警告"""
    if not recent_states or len(recent_states) < 4:
        return "无异常"

    last_4 = recent_states[-4:]
    last_5 = recent_states[-5:] if len(recent_states) >= 5 else recent_states

    # 检测连续4步同一状态
    if len(set(last_4)) == 1:
        state_id = last_4[0]
        if state_id in feature_tree.states:
            state = feature_tree.states[state_id]
            return f"""
⚠️⚠️⚠️ **检测到循环！** ⚠️⚠️⚠️

- **当前状态**: {state.state_name} ({state_id})
- **停留时长**: 连续{len([s for s in last_5 if s == state_id])}步
- **已访问次数**: {state.visited_count}次
- **在此状态执行的步骤**: {', '.join(state.steps_in_this_state)}

**强烈建议**：
1. 如果弹窗或子功能已充分探索 → 点击Back/关闭按钮返回
2. 如果操作反复失败 → 放弃当前路径，切换到其他功能
3. **不要再继续在同一状态重复相同操作！**
"""

    # 检测频繁往返（A→B→A→B）
    if len(recent_states) >= 4:
        if recent_states[-1] == recent_states[-3] and recent_states[-2] == recent_states[-4]:
            return f"""
⚠️ **检测到往返循环！**

- 过去4步在 {recent_states[-1]} 和 {recent_states[-2]} 之间反复跳转
- 建议：停止当前路径，尝试新的探索方向
"""

    return "无异常"

def _format_current_feature_history(self, current_feature: dict, feature_tree: FeatureTree) -> str:
    """格式化当前功能的探索历史"""
    feature_path = current_feature.get('feature_path', [])

    # 简化版：统计功能树中的状态
    total_states = len(feature_tree.states)
    total_transitions = len(feature_tree.state_transitions)

    return f"""
- 已探索状态数: {total_states}
- 状态转移次数: {total_transitions}
- 当前功能路径: {' -> '.join(feature_path)}
"""
```

### 5.3 方案4：硬编码循环检测（快速实施）⭐

在 `explorer.py` 主循环中添加循环检测：

```python
# explorer.py:198 主循环开始前
self.recent_state_history = []  # 初始化状态历史

# explorer.py:241 在 record_step 之后
# ⭐ 记录状态历史
if executor_result.screen_after and self.feature_tree_builder:
    state_id = self.state_identifier.identify_state(
        executor_result.screen_after,
        after_perception
    )
    self.recent_state_history.append(state_id)
    if len(self.recent_state_history) > 10:
        self.recent_state_history.pop(0)

    # ⭐ 循环检测：连续4步同一状态
    if len(self.recent_state_history) >= 4:
        last_4 = self.recent_state_history[-4:]
        if len(set(last_4)) == 1:  # 全部相同
            logger.warning(f"⚠️⚠️⚠️ 检测到循环：连续4步停留在 {last_4[0]}")
            logger.warning("强制执行Back操作返回上一级")

            # 创建强制Back步骤
            back_step = ExplorationStep(
                step_id=f"{next_step.step_id}_auto_back",
                instruction="检测到循环，执行Back返回上一级",
                sub_goal="退出当前循环状态",
                status="pending",
                enable_reflection=False,
                max_iterations=1
            )

            # 执行Back
            back_result = await self.executor.execute(
                instruction=back_step.instruction,
                plan_context={
                    "overall_plan": "自动退出循环",
                    "current_sub_goal": "返回上一级"
                },
                enable_reflection=False,
                max_iterations=1
            )

            # 清空状态历史
            self.recent_state_history = []

            logger.success("已自动退出循环状态")
```

---

## 六、实施优先级

### 阶段1：快速修复（1-2小时）⭐ 立即实施

1. **方案4：硬编码循环检测**
   - 在主循环添加状态历史记录
   - 检测连续4步同一状态
   - 强制执行Back
   - **效果**: 立即阻止长时间循环

### 阶段2：增强感知（2-3小时）

2. **方案1：增强Planner上下文**
   - 修改 `replan()` 签名
   - 传递 `feature_tree` 和 `recent_state_sequence`
   - 在Prompt中添加历史信息和循环警告
   - **效果**: LLM获得循环感知能力

### 阶段3：智能判断（2-3小时）

3. **方案3：功能完成度评估**
   - 在Prompt中添加完成度判断任务
   - 输出格式中要求 `feature_completion_assessment`
   - 根据完成度自动插入返回步骤
   - **效果**: 智能终止探索，避免过度

---

## 七、总结

### 当前问题

| 问题 | 根本原因 | 影响 |
|------|---------|------|
| **循环探索** | Planner缺少历史状态信息 | 在同一状态停留5+步 |
| **无法退出** | 没有功能完成度判断机制 | 不知道何时该返回 |
| **重复操作** | 没有循环检测提示 | 反复执行相似指令 |

### 解决策略

```
短期（快速见效）：
  └── 方案4：硬编码循环检测（强制Back）

中期（根本解决）：
  └── 方案1：增强Planner上下文
        ├── 传递feature_tree
        ├── 传递recent_state_sequence
        └── Prompt中添加循环警告

长期（智能优化）：
  └── 方案3：功能完成度评估
        └── LLM自主判断何时结束探索
```

### 预期效果

| 指标 | 修复前 | 修复后 | 提升 |
|------|--------|--------|------|
| 循环检测率 | 0% | 100% | ✅ |
| 自动退出循环 | 不支持 | 4步内 | ✅ |
| LLM循环感知 | 无 | 有（历史+警告） | ✅ |
| 探索效率 | 5步/0状态 | 1.5步/状态 | +300% |

---

## 八、下一步行动

1. **立即实施方案4**（硬编码循环检测）
   - 估计时间：1小时
   - 文件修改：`explorer.py`
   - 测试：运行之前的问题案例，验证是否能在4步内退出

2. **准备实施方案1**（增强Planner上下文）
   - 估计时间：2-3小时
   - 文件修改：`planner.py`, `explorer.py`
   - 测试：对比修复前后的Prompt，确认信息完整性

3. **观察实际效果**（1-2天）
   - 运行多个探索任务
   - 收集循环检测触发次数
   - 分析是否有误判（正常探索被判定为循环）

4. **根据效果决定是否实施方案3**（功能完成度评估）
   - 如果方案4+方案1效果良好，可暂缓方案3
   - 如果仍有边界场景问题，继续实施方案3
