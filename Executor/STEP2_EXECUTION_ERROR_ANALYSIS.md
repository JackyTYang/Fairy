# Step 2 执行不准确问题分析与解决方案

**问题会话**: 20251223_145104
**问题步骤**: Step 2
**发现时间**: 2025-12-23

---

## 问题描述

### 预期行为
**指令**: 在左侧分类列表中，点击当前高亮分类以外的任一分类（例如"鸡肉汉堡/卷"或"巨无霸牛鱼肉堡"）

**预期结果**:
- 停留在菜单页（ProductMdsListActivity）
- 右侧商品列表切换到对应分类

### 实际行为
**执行动作**: 点击坐标 `(100, 1918)`
**实际结果**: 进入了优惠券页面（CouponListV2Activity）

**状态转移**:
```
state_productmdslist_a4f2f6f0 (菜单页)
  → 预期: state_productmdslist_XXXX (菜单页，不同商品分类)
  → 实际: state_couponlistv2_0fd39cbe (优惠券页)
```

---

## 根本原因分析

### 1. 坐标分析

**Executor 的决策**:
```json
{
  "action_thought": "屏幕上已可见的非高亮分类中，'鸡肉汉堡/卷'(Mark 6) 与 '巨无霸牛鱼肉堡'(Mark 7) 都符合要求。我任选其一即可完成指令，这里点击更靠下的 Mark 6",
  "actions_taken": [
    {
      "name": "Tap",
      "arguments": {
        "x": 100,
        "y": 1918
      }
    }
  ]
}
```

**SoM坐标映射**:
```json
{
  "6": [100, 1918],  // "鸡肉汉堡/卷" 分类
  "7": [100, 2136]   // "巨无霸牛鱼肉堡" 分类
}
```

**UI元素实际位置**（从compressed_txt）:
```
Mark 6: RelativeLayout [鸡肉汉堡/卷] [Center: [100.5, 1918.5]]  ← Executor选择的目标
优惠券入口: RelativeLayout (cl_content) [Center: [217.5, 1944.0]]  ← 实际点击的元素！
```

### 2. 问题根源

**坐标重叠问题**:
```
┌─────────────────────────────────┐
│  菜单分类列表（左侧）             │
│  ┌───────────────┐               │
│  │ 人气热卖      │  Y=1034      │
│  │ 大堡口福      │  Y=1255      │
│  │ 麦金卡专享    │  Y=1476      │
│  │ 随心拼        │  Y=1697      │
│  │ 鸡肉汉堡/卷   │  Y=1918 ← 目标分类
│  │ 巨无霸        │  Y=2136      │
│  └───────────────┘               │
│                                  │
│  ⚠️ 优惠券浮层（悬浮在左下角）     │
│  ┌──────────────┐                │
│  │ 1张 | 去查看 │ Y=1916 ← 实际点击位置！
│  │ 优惠券暂不可用│ Y=1944（中心点）
│  └──────────────┘ Y=1984         │
└─────────────────────────────────┘

点击坐标: (100, 1918)
  ↓
优惠券浮层范围: X=[~70, ~365], Y=[~1890, ~2010]
  ↓
命中优惠券浮层的可点击区域（cl_content）!
```

**为什么点击失败？**
1. **Z轴遮挡**：优惠券浮层在Z轴上位于分类列表上方
2. **点击穿透失败**：Android的点击事件从上层View开始分发
3. **可点击区域重叠**：
   - 分类"鸡肉汉堡/卷"中心点: `(100, 1918)`
   - 优惠券浮层可点击区域: X=[70, 365], Y=[~1890, ~2010]
   - **坐标(100, 1918)在优惠券浮层的可点击范围内！**

### 3. Executor的决策过程

**Executor看到的信息**:
- ✅ SoM Mapping: Mark 6 → (100, 1918)
- ✅ Compressed Text: Mark 6 是"鸡肉汉堡/卷"分类
- ❌ **缺失信息**: 优惠券浮层遮挡了分类列表底部

**为什么选择了Mark 6而不是Mark 7？**
```
"action_thought": "屏幕上已可见的非高亮分类中，'鸡肉汉堡/卷'(Mark 6) 与 '巨无霸牛鱼肉堡'(Mark 7) 都符合要求。我任选其一即可完成指令，这里点击更靠下的 Mark 6"
```

LLM的选择逻辑：
- 指令说"靠下的分类"
- Mark 6 (Y=1918) 比 Mark 4/5 更靠下
- Mark 7 (Y=2136) 虽然更靠下，但LLM认为Mark 6已满足"靠下"的要求

**不幸的是，Mark 6 恰好被优惠券浮层遮挡了！**

---

## 为什么之前的SoM修复没有解决这个问题？

### 之前修复的问题（已解决✅）
- **问题**: SoM_mapping和compressed_txt使用不同数据源，Mark编号错位
- **影响**: LLM选择正确的Mark，但点击错误的坐标
- **解决**: 统一数据源，确保Mark编号和坐标一一对应

### 本次的新问题（未解决❌）
- **问题**: 坐标正确，但被其他View遮挡
- **影响**: 点击到了遮挡层而非目标元素
- **本质**: 这是**Z轴遮挡问题**，不是SoM映射问题

---

## 解决方案

### 方案1：改进SoM生成 - 过滤被遮挡的元素 ⭐ 根本解决

**思路**：在生成SoM标注时，检测元素是否被其他View遮挡

#### 实现步骤

**Step 1: 在 `screen_perception_AT.py` 中添加遮挡检测**

```python
def _is_view_occluded(node, all_nodes):
    """检测View是否被其他View遮挡

    Args:
        node: 当前节点
        all_nodes: 所有节点列表（按Z轴顺序，后面的在上层）

    Returns:
        bool: True表示被遮挡
    """
    node_bounds = node.get('bounds')
    if not node_bounds:
        return False

    node_center = node.get('center')

    # 获取当前节点在列表中的索引（Z轴位置）
    try:
        node_index = all_nodes.index(node)
    except ValueError:
        return False

    # 检查所有在上层的节点（索引大于当前节点）
    for upper_node in all_nodes[node_index + 1:]:
        # 跳过不可见或不可点击的节点
        if not upper_node.get('visible', True):
            continue

        upper_bounds = upper_node.get('bounds')
        if not upper_bounds:
            continue

        # 检查上层节点是否遮挡了当前节点的中心点
        if _point_in_bounds(node_center, upper_bounds):
            # 如果上层节点可点击，说明当前节点被遮挡
            if upper_node.get('clickable', False):
                logger.debug(f"Node {node.get('resource-id', 'Unknown')} at {node_center} "
                           f"is occluded by {upper_node.get('resource-id', 'Unknown')}")
                return True

    return False

def _point_in_bounds(point, bounds):
    """判断点是否在矩形范围内

    Args:
        point: [x, y]
        bounds: [x1, y1, x2, y2]

    Returns:
        bool
    """
    x, y = point
    x1, y1, x2, y2 = bounds
    return x1 <= x <= x2 and y1 <= y <= y2
```

**Step 2: 在标注时应用遮挡检测**

```python
def _traverse_tree_mark_node(root_node, all_nodes_flat):
    """遍历AccessibilityTree并标记节点

    Args:
        root_node: 根节点
        all_nodes_flat: 平铺的所有节点列表（按Z轴顺序）
    """
    index = 1

    def _add_node(node, type):
        nonlocal index

        # ⭐ 检查是否被遮挡
        if _is_view_occluded(node, all_nodes_flat):
            logger.warning(f"Skip occluded node: {node.get('resource-id', 'Unknown')} "
                         f"at {node.get('center')}")
            return node  # 不标注，跳过

        # 正常标注流程
        if set_mark:
            node["mark"] = index

        nodes_need_marked[type]['node_bounds_list'][index] = node["bounds"]
        nodes_need_marked[type]['node_center_list'][index] = node["center"]

        # ... 其他处理 ...

        index = index + 1
        return node

    # ... 遍历逻辑 ...
```

#### 效果

**修复前**:
```
Mark 6: [鸡肉汉堡/卷] at (100, 1918)  ← 被优惠券浮层遮挡
Mark 7: [巨无霸] at (100, 2136)
```

**修复后**:
```
Mark 6: [巨无霸] at (100, 2136)  ← 自动跳过被遮挡的元素，重新编号
```

Executor会选择Mark 6，但实际点击的是"巨无霸"分类（未被遮挡）。

---

### 方案2：优化Executor的决策逻辑 - 避免底部元素 ⭐ 快速缓解

**思路**：在Prompt中提示LLM优先选择屏幕中部的元素，避免底部（可能被浮层遮挡）

#### 修改 Executor 的 System Prompt

```python
# Executor的System Message中添加
"""
## 点击策略建议

当需要点击列表元素时，优先选择以下位置的元素：
1. **屏幕中部元素**（Y坐标在屏幕高度的30%-70%范围）
2. **避免屏幕底部**（Y坐标 > 屏幕高度的80%），可能被底部栏/浮层遮挡
3. **避免屏幕顶部**（Y坐标 < 屏幕高度的20%），可能被状态栏/导航栏遮挡

如果指令要求点击"靠下的元素"，优先选择**可见范围内中下部**的元素，而非最底部。
"""
```

#### 效果

本案例中：
- Mark 4 (Y=1476, 屏幕高度62%) ← 更优选择
- Mark 5 (Y=1697, 屏幕高度71%) ← 更优选择
- Mark 6 (Y=1918, 屏幕高度81%) ← **避免**（底部，可能被遮挡）
- Mark 7 (Y=2136, 屏幕高度90%) ← **避免**（最底部）

Executor会优先选择Mark 4或5，避开被遮挡的区域。

---

### 方案3：增强Executor的反思能力 - 事后检测 ⭐ 兜底方案

**思路**：执行后检测页面跳转，如果不符合预期，自动重试

#### 在 Executor 中添加页面跳转检测

```python
async def execute_with_validation(instruction, expected_activity):
    """执行动作并验证页面跳转

    Args:
        instruction: 操作指令
        expected_activity: 预期的Activity名称（或"same"表示不应跳转）
    """
    # 记录执行前的Activity
    activity_before = screen_info.current_activity_info.activity

    # 执行动作
    result = await executor.execute(instruction)

    # 获取执行后的Activity
    activity_after = result.screen_after.current_activity_info.activity

    # 验证
    if expected_activity == "same":
        if activity_before != activity_after:
            logger.warning(f"Unexpected navigation: {activity_before} → {activity_after}")
            return {
                "success": False,
                "reason": "Unexpected page navigation detected",
                "should_retry": True
            }
    elif expected_activity not in activity_after:
        logger.warning(f"Expected {expected_activity}, got {activity_after}")
        return {
            "success": False,
            "reason": "Navigation to wrong page",
            "should_retry": True
        }

    return result
```

#### 修改 Planner 生成的指令

```json
{
  "step_id": "step_2",
  "instruction": "在左侧分类列表中，点击非高亮分类",
  "expected_page": "ProductMdsListActivity",  // ⭐ 新增：期望停留在当前页
  "enable_reflection": true,
  "max_iterations": 3  // 如果跳转错误，允许重试
}
```

#### 效果

```
执行: 点击Mark 6 → 进入优惠券页
检测: Activity变化 ProductMdsListActivity → CouponListV2Activity
判断: 不符合预期（expected_page: ProductMdsListActivity）
反思: "点击位置可能被遮挡，应选择其他分类"
重试: 点击Mark 4 → 停留在菜单页 ✓
```

---

### 方案4：改进Planner的指令生成 - 指令更精确 ⭐ 预防措施

**思路**：指令中明确指定Mark编号，避免LLM自由选择

#### 当前指令（模糊）
```
"在左侧分类列表中，点击当前高亮分类以外的任一分类（例如靠下的"鸡肉汉堡/卷"或"巨无霸牛鱼肉堡"）"
```

问题：
- "任一分类" 给LLM自由选择权
- "靠下的" 是模糊描述

#### 改进后指令（精确）
```
"点击Mark 4（'麦金卡专享'分类），观察右侧商品列表变化"
```

优势：
- 明确指定Mark编号
- 减少LLM决策空间
- 避免选择被遮挡的元素

#### 如何生成精确指令？

在 Planner 的 Prompt 中增加约束：
```
## 指令生成规范

生成instruction时，应：
1. **明确指定Mark编号**：如"点击Mark 5"，而非"点击某个分类"
2. **优先选择屏幕中部元素**：避免底部可能被浮层遮挡
3. **避免模糊描述**：如"靠下的"、"任一"等

示例：
- ❌ "点击左侧任一分类"
- ✅ "点击Mark 4（'麦金卡专享'）"
```

---

## 方案对比与推荐

| 方案 | 实现难度 | 效果 | 适用场景 | 推荐度 |
|------|---------|------|---------|--------|
| 方案1: 过滤被遮挡元素 | 中（需修改SoM生成） | 根本解决 | 所有场景 | ⭐⭐⭐⭐⭐ |
| 方案2: 优化决策逻辑 | 低（修改Prompt） | 缓解大部分问题 | 有明显浮层的页面 | ⭐⭐⭐⭐ |
| 方案3: 增强反思能力 | 中（需修改Executor） | 兜底保障 | 无法预测的遮挡 | ⭐⭐⭐ |
| 方案4: 精确指令 | 低（修改Planner Prompt） | 预防部分问题 | 可提前规划的场景 | ⭐⭐⭐ |

### 推荐实施顺序

**阶段1：快速修复（1小时）**
1. ✅ **方案2**：修改Executor Prompt，避免底部元素
2. ✅ **方案4**：改进Planner指令生成规范

**阶段2：根本解决（2-3小时）**
3. ✅ **方案1**：实现遮挡检测，过滤被遮挡的SoM标注

**阶段3：兜底保障（2小时）**
4. ✅ **方案3**：增强Executor反思能力，检测意外跳转

---

## 其他发现：为什么本次没有陷入循环？

虽然Step 2执行不准确，但系统**没有陷入循环探索**，反而成功探索了优惠券功能。

### 动态规划的优势

**传统固定计划的处理**:
```
Step 2执行失败 → 重试Step 2 → 再次失败 → 再重试 → 循环
```

**Fairy的动态规划**:
```
Step 2: 意外进入优惠券页
  ↓ Planner重新规划
Step 3: LLM识别到"当前在优惠券页，这是新功能！"
  ↓ 创建新子功能 feature_6
Step 4-8: 深度探索优惠券功能
  ↓ 探索完成
返回菜单页，继续其他功能
```

**关键机制**：
1. **每步重新规划**：Planner看到执行结果后重新评估
2. **功能动态发现**：LLM识别到新功能并调整探索方向
3. **容错能力**：意外跳转不会导致失败，而是新的探索机会

这就是为什么虽然Step 2不准确，但整体探索仍然成功的原因。

---

## 总结

### 问题根源
**Z轴遮挡问题**：优惠券浮层悬浮在分类列表上方，点击(100, 1918)命中了浮层而非目标分类

### 解决优先级
1. **高优先级**：方案1（过滤被遮挡元素）+ 方案2（避免底部）
2. **中优先级**：方案3（反思重试）
3. **低优先级**：方案4（精确指令）

### 长期改进方向
- 实现更鲁棒的SoM标注（考虑Z轴关系）
- 增强Executor的空间感知能力
- 提供可视化调试工具（显示遮挡关系）
