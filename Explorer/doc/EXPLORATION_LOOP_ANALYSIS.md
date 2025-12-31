# Explorer 重复探索问题分析与解决方案

## 问题重现

**会话**: `20251220_172306`
**重复探索的功能**: "配送时间选择弹窗"（"请选择您的送达时间"）
**重复的步骤**: Step 3-7（共5个步骤）

### 重复行为表现

| 步骤 | 指令 | 实际操作 | 状态转移 |
|------|------|---------|---------|
| Step 3 | 点击"预约送餐"并观察选中态 | ✓ 成功切换 | `state_e960fb61` → `state_e960fb61` |
| Step 4 | 保持预约状态，点击"确定" | ❌ 反而点击了"预约"按钮重新打开弹窗 | `state_e960fb61` → `state_e960fb61` |
| Step 5 | 点击弹窗外部背景关闭弹窗 | ❌ 失败（弹窗不支持点背景关闭） | `state_e960fb61` → `state_e960fb61` |
| Step 6 | 再次点击"预约送餐"并观察 | ✓ 重复 Step 3 | `state_e960fb61` → `state_e960fb61` |
| Step 7 | 点击"尽快送达"并观察选中态 | ✓ 成功切换 | `state_e960fb61` → `state_e960fb61` |

**结果**：在同一个弹窗内反复切换"预约送餐"和"尽快送达"，没有任何进展。

---

## 根本原因分析

### 1. **状态识别粒度不足**

**问题**：`StateIdentifier` 基于 Activity + UI哈希 识别状态，但：

```python
# state_identifier.py:46
state_id = f"state_{activity_short}_{ui_hash}"
```

- **弹窗打开前**：`state_productmdslist_e960fb61`（菜单页）
- **弹窗打开后**：`state_productmdslist_e960fb61`（菜单页 + 弹窗）

UI哈希过滤了动态内容（数字、时间），导致：
- 弹窗内部切换"预约送餐"和"尽快送达"时，UI结构基本一致
- 哈希值相同，无法区分"弹窗打开"和"弹窗关闭"两个状态

**影响**：
- StateTracker 误认为一直在同一个状态
- 没有触发"新状态发现"的逻辑
- 没有终止当前功能探索的信号

### 2. **缺少功能完成度判断**

**问题**：Planner 没有判断"当前功能是否已探索完毕"

在 `planner.py:463` 的 Replan Prompt 中：

```python
### 1. 功能状态判断 ⭐ 重要
请根据当前页面的实际内容判断：

**A. 是否还在当前功能中？**
- 当前功能路径: {' -> '.join(current_plan.current_feature.get('feature_path', [...]))}
- 如果仍在此功能中，继续探索
- 如果不在，进入下一步判断
```

但是**没有明确提示LLM**：
- ✅ "如果功能已充分探索，应该结束并返回"
- ✅ "如果连续多次在同一状态，应该意识到陷入循环"

### 3. **没有提供历史探索记录**

**问题**：Planner 提供的上下文中缺少：

当前传递给LLM的信息：
- ✅ 已完成的步骤列表（`completed_summary`）
- ✅ 上一步执行结果（`last_result`）
- ✅ 导航路径（`navigation_path`）
- ❌ **已探索过的功能列表**
- ❌ **当前功能已执行的操作历史**
- ❌ **状态转移历史**

结果：
- LLM不知道"预约送餐"的选中态已经在 Step 3 观察过了
- LLM不知道自己已经在同一个弹窗里重复操作了5次
- LLM不知道该功能已经探索完毕，应该返回上一级

### 4. **Feature Tree 与 Planner 的信息断层**

**问题**：`FeatureTreeBuilder` 记录了丰富的状态信息，但没有传递给 Planner

`FeatureTreeBuilder` 已经有：
- 所有已探索的状态（`tree.states`）
- 状态转移关系（`tree.state_transitions`）
- 每个状态的可达状态（`state.reachable_states`）

但 `planner.py:replan()` 只接收：
```python
async def replan(
    self,
    target: ExplorationTarget,
    current_plan: ExplorationPlan,
    current_perception: PerceptionOutput,
    last_step: ExplorationStep,
    last_executor_result: dict,
    navigation_path: list  # ⚠️ 仅有路径名称，没有状态转移历史
) -> ExplorationPlan:
```

**缺少**：
- `feature_tree: FeatureTree` - 完整的功能树
- `state_transitions: List[Transition]` - 状态转移历史
- `current_state_history: List[str]` - 最近访问的状态序列

---

## 解决方案

### 方案 1：增强 Planner 的上下文感知 ⭐ 推荐

**核心思路**：让 Planner 看到"历史探索状态"，避免重复操作

#### 1.1 传递状态转移历史

修改 `planner.py:replan()` 方法签名：

```python
async def replan(
    self,
    target: ExplorationTarget,
    current_plan: ExplorationPlan,
    current_perception: PerceptionOutput,
    last_step: ExplorationStep,
    last_executor_result: dict,
    navigation_path: list,
    feature_tree: FeatureTree,  # ⭐ 新增：完整功能树
    recent_state_sequence: List[str]  # ⭐ 新增：最近10个状态ID
) -> ExplorationPlan:
```

#### 1.2 在 Replan Prompt 中添加历史信息

在 `_build_replan_prompt()` 中添加：

```python
## 历史探索状态 ⚠️ 避免重复

### 最近访问的状态序列
{self._format_recent_states(recent_state_sequence, feature_tree)}

### 当前功能的探索历史
{self._format_current_feature_history(current_plan.current_feature, feature_tree)}

### 状态转移分析
- 过去5步状态转移: {self._format_recent_transitions(feature_tree)}
- **警告**: 如果连续3步以上停留在同一状态，说明可能陷入循环！
- **建议**: 如果当前功能的核心操作已探索完毕，应该：
  1. 点击返回/关闭按钮返回上一级
  2. 或切换到其他未探索的子功能
```

#### 1.3 添加循环检测提示

```python
## 循环检测 ⚠️

**当前状态**: {current_state_id}
**过去5步的状态**: {', '.join(recent_state_sequence[-5:])}

**分析**：
- 如果过去3步以上都是同一状态 → 可能陷入循环
- 如果当前指令与已完成步骤中的指令高度相似 → 可能重复操作

**应对策略**：
1. 检查是否已完成当前功能的探索目标
2. 如果已完成，使用Back或关闭按钮返回
3. 如果未完成但陷入循环，尝试不同的操作方式（如滑动、长按）
4. 如果多次失败，放弃当前路径，切换到其他功能
```

#### 1.4 实现辅助格式化方法

```python
def _format_recent_states(self, recent_states: List[str], feature_tree: FeatureTree) -> str:
    """格式化最近访问的状态序列"""
    lines = []
    for i, state_id in enumerate(recent_states[-5:]):
        if state_id in feature_tree.states:
            state = feature_tree.states[state_id]
            lines.append(f"{i+1}. {state.state_name} ({state.activity_name})")
        else:
            lines.append(f"{i+1}. {state_id}")
    return "\n".join(lines)

def _format_current_feature_history(self, current_feature: dict, feature_tree: FeatureTree) -> str:
    """格式化当前功能的探索历史"""
    feature_path = current_feature.get('feature_path', [])

    # 找到当前功能已探索的所有状态
    # （从feature_tree中查找属于当前功能路径的状态）
    explored_states = []
    for state_id, state in feature_tree.states.items():
        # 简化版：列出所有状态（完整版需要匹配功能路径）
        explored_states.append(f"- {state.state_name}: {len(state.reachable_states)} 个可达状态")

    return "\n".join(explored_states) if explored_states else "当前功能尚未探索任何状态"

def _format_recent_transitions(self, feature_tree: FeatureTree) -> str:
    """格式化最近的状态转移"""
    recent = feature_tree.state_transitions[-5:] if len(feature_tree.state_transitions) >= 5 else feature_tree.state_transitions

    lines = []
    for trans in recent:
        if trans['from'] == trans['to']:
            lines.append(f"- {trans['step']}: {trans['from']} → 自身（⚠️ 无转移）")
        else:
            lines.append(f"- {trans['step']}: {trans['from']} → {trans['to']}")

    return "\n".join(lines)
```

#### 1.5 在 Explorer 主循环中传递参数

修改 `explorer.py` 的 Planner 调用：

```python
# 获取最近10个状态序列
recent_states = [
    step['to_state_id']
    for step in self.state_tracker.navigation_path[-10:]
]

new_plan = await self.planner.replan(
    target=self.target,
    current_plan=self.current_plan,
    current_perception=stable_perception,
    last_step=step,
    last_executor_result=executor_result,
    navigation_path=self.state_tracker.navigation_path,
    feature_tree=self.feature_tree_builder.tree,  # ⭐ 新增
    recent_state_sequence=recent_states  # ⭐ 新增
)
```

---

### 方案 2：改进 State 识别粒度

**核心思路**：让弹窗打开/关闭成为不同的状态

#### 2.1 检测弹窗层

在 `StateIdentifier._hash_ui_structure()` 中：

```python
def _hash_ui_structure(self, perception_output) -> str:
    """基于UI结构生成哈希，考虑弹窗层"""
    try:
        with open(perception_output.compressed_txt_path, 'r', encoding='utf-8') as f:
            ui_text = f.read()

        # ⭐ 检测弹窗特征
        dialog_markers = [
            'Dialog', 'Popup', 'Modal', '弹窗', '请选择',
            'view_dialog_bg', 'dialog_', 'popup_'
        ]
        has_dialog = any(marker in ui_text for marker in dialog_markers)

        # ⭐ 在哈希中加入弹窗标记
        ui_text_with_dialog = f"[DIALOG:{has_dialog}]" + ui_text

        filtered_text = self._filter_dynamic_content(ui_text_with_dialog)
        hash_obj = hashlib.md5(filtered_text.encode('utf-8'))
        return hash_obj.hexdigest()[:8]

    except Exception as e:
        logger.warning(f"UI哈希生成失败: {e}")
        import time
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
```

**优点**：
- 简单直接，弹窗打开/关闭会产生不同的 state_id
- 触发 StateTracker 的"新状态"逻辑

**缺点**：
- 弹窗内部切换"预约"和"尽快"仍然是同一状态
- 治标不治本，仍需方案1的历史感知

---

### 方案 3：引入功能完成度判断 ⭐ 配合方案1使用

**核心思路**：让LLM明确判断"功能是否已探索完毕"

#### 3.1 在 Replan Prompt 中添加完成度判断任务

```python
## 功能完成度评估 ⭐ 必须回答

对于当前功能：{' -> '.join(current_plan.current_feature.get('feature_path', []))}

请回答以下问题：
1. **核心元素是否已识别？**
   - 这个功能的主要按钮/选项/输入框是否都已发现？

2. **核心交互是否已测试？**
   - 主要的点击/切换/选择操作是否都已执行并观察结果？

3. **页面状态是否已遍历？**
   - 不同模式/选项的界面差异是否都已记录？

4. **是否需要继续深入？**
   - 是否有未探索的子页面/子功能？
   - 还是应该返回上一级？

**判断标准**：
- ✅ 如果核心元素已识别 + 核心交互已测试 + 无子页面 → 功能完成，应返回
- ⚠️ 如果仅在同一页面反复切换选项 → 可能过度探索，应返回
- ❌ 如果有子页面未进入 → 功能未完成，应深入探索
```

#### 3.2 在输出格式中要求明确回答

```json
{
  "feature_completion_assessment": {
    "is_completed": true/false,
    "completion_rate": "70%",
    "reason": "已识别所有按钮，已测试模式切换，无子页面",
    "should_return": true/false,
    "next_action_type": "return_to_parent" | "explore_deeper" | "continue_current"
  },
  "plan_thought": "...",
  "steps": [...]
}
```

#### 3.3 根据完成度自动添加"返回"步骤

在 `planner.py` 解析响应后：

```python
def _parse_plan_response(self, response: str, ...) -> ExplorationPlan:
    # ... 原有解析逻辑 ...

    response_json = json.loads(response)

    # ⭐ 检查功能完成度
    completion = response_json.get('feature_completion_assessment', {})
    if completion.get('should_return', False):
        # 在步骤列表开头插入"返回"步骤
        return_step = ExplorationStep(
            step_id=f"step_{next_step_num}",
            instruction="使用Back或关闭按钮返回上一级页面",
            sub_goal="结束当前功能探索，返回上一级",
            status="pending",
            enable_reflection=False,
            max_iterations=1
        )
        steps.insert(0, return_step)
        logger.info(f"功能已完成（{completion.get('reason')}），自动添加返回步骤")

    # ... 构建 ExplorationPlan ...
```

---

### 方案 4：简化版 - 状态重复检测 ⭐ 快速实现

**核心思路**：在 `explorer.py` 主循环中检测状态重复，强制退出循环

```python
# explorer.py 主循环中

# 记录状态历史（保留最近10个）
if not hasattr(self, 'recent_state_history'):
    self.recent_state_history = []

self.recent_state_history.append(current_state_id)
if len(self.recent_state_history) > 10:
    self.recent_state_history.pop(0)

# ⭐ 检测循环：如果连续4步都是同一状态
if len(self.recent_state_history) >= 4:
    last_4 = self.recent_state_history[-4:]
    if len(set(last_4)) == 1:  # 全部相同
        logger.warning(f"检测到循环：连续4步停留在 {last_4[0]}")
        logger.warning("强制执行Back操作返回上一级")

        # 执行Back
        back_step = ExplorationStep(
            step_id=f"step_{step_counter}_back",
            instruction="检测到循环，执行Back返回",
            sub_goal="退出当前循环",
            status="pending",
            enable_reflection=False,
            max_iterations=1
        )

        executor_result = await self.executor_wrapper.execute_step(
            step=back_step,
            screen_info=screen_info,
            perception_infos=stable_perception
        )

        # 清空状态历史
        self.recent_state_history = []
        continue
```

**优点**：
- 实现简单，立即见效
- 不依赖LLM判断

**缺点**：
- 硬编码阈值（4步），可能误判
- 没有从根本上提升LLM的理解能力

---

## 推荐实施方案

### 阶段1：快速修复（1-2小时）
1. ✅ **方案4**：在主循环添加循环检测，强制Back
2. ✅ **方案2部分**：改进弹窗检测

### 阶段2：增强感知（2-3小时）
3. ✅ **方案1**：传递 `feature_tree` 和 `recent_state_sequence` 给 Planner
4. ✅ 在 Replan Prompt 中添加历史状态和循环检测提示

### 阶段3：智能判断（2-3小时）
5. ✅ **方案3**：添加功能完成度评估
6. ✅ 根据完成度自动插入返回步骤

---

## 预期效果

### 修复前
```
Step 3: 点击"预约送餐" → state_e960fb61
Step 4: 点击"预约"按钮 → state_e960fb61
Step 5: 点击背景关闭 → state_e960fb61
Step 6: 再次点击"预约送餐" → state_e960fb61
Step 7: 点击"尽快送达" → state_e960fb61
（陷入循环，5步无进展）
```

### 修复后（方案4）
```
Step 3: 点击"预约送餐" → state_e960fb61
Step 4: 点击"预约"按钮 → state_e960fb61
Step 5: 点击背景关闭 → state_e960fb61
Step 6: 再次点击"预约送餐" → state_e960fb61
⚠️ 检测到循环，强制Back
Step 7: Back → state_c8ca423f（返回菜单页）
（继续探索其他功能）
```

### 修复后（方案1+3）
```
Step 3: 点击"预约送餐" → state_e960fb61_dialog
（LLM看到：弹窗已打开，预约模式已切换）

Step 4: 功能完成度评估 = 已完成
  - 理由：两种模式已测试，界面差异已记录，无子页面
  - 自动插入返回步骤

Step 4: 点击"确定"关闭弹窗 → state_e960fb61
（继续探索其他功能）
```

---

## 实施建议

1. **先实施方案4（循环检测）** - 立即见效，防止长时间卡死
2. **再实施方案1（历史感知）** - 提升LLM决策质量
3. **最后实施方案3（完成度判断）** - 实现智能探索终止

这样可以在短期内解决眼前问题，同时逐步提升系统的智能性。
