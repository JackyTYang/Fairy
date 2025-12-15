# FairyExecutor 反思循环功能说明

## 🎯 功能概述

为 FairyExecutor 添加了 **反思循环机制**，解决了"一个 instruction 需要多步才能完成"的问题。

### 问题场景

之前的实现：
```python
# 问题：这个任务可能需要滑动多次才能找到目标
result = await executor.execute("向下滑动找到板烧鸡腿堡")
# ❌ 只滑动一次就退出了！
```

现在的实现：
```python
# ✅ 自动循环直到找到目标
result = await executor.execute(
    "向下滑动找到板烧鸡腿堡",
    enable_reflection=True,  # 启用反思
    max_iterations=5         # 最多尝试5次
)
```

---

## 🔧 实现细节

### 核心组件

提取自 Fairy 原始框架的 `AppReflectorAgent`，集成到 `FairyExecutor`：

1. **`_reflect_on_execution()`** - 主反思方法
   - 调用 LLM 分析执行前后的屏幕变化
   - 判断任务完成状态

2. **`_build_reflection_prompt()`** - 构建反思 Prompt
   - 对比执行前后的屏幕
   - 提供反思步骤指导

3. **`_parse_reflection_response()`** - 解析 LLM 响应
   - 提取 action_result (A/B/C/D)
   - 提取 progress_status 和错误原因

### 执行流程

```
用户调用 execute(instruction, enable_reflection=True)
    ↓
循环开始 (最多 max_iterations 次)
    ↓
    1. 获取屏幕（before）
    ↓
    2. LLM 决策动作
    ↓
    3. 执行动作
    ↓
    4. 获取屏幕（after）
    ↓
    5. ⭐ 反思：任务完成了吗？
       - A: 完全成功 → 退出循环 ✓
       - B: 部分成功 → 继续循环 ⟳
       - C/D: 失败 → 继续尝试或退出 ✗
    ↓
    根据反思结果决定是否继续
循环结束
```

---

## 📖 使用方法

### 基本用法

```python
from Executor import ExecutorConfig, FairyExecutor

config = ExecutorConfig.from_env()
executor = FairyExecutor(config)

# 启用反思，自动循环直到完成
result = await executor.execute(
    instruction="向下滑动找到板烧鸡腿堡套餐",
    enable_reflection=True,  # ⭐ 关键参数
    max_iterations=5         # 最多尝试5次
)

print(f"迭代次数: {result.iterations}")
print(f"最终状态: {result.progress_info.action_result}")
```

### 禁用反思（传统模式）

```python
# 执行一次就退出，与之前行为一致
result = await executor.execute(
    instruction="点击按钮",
    enable_reflection=False  # 禁用反思
)
```

### 复杂任务序列

```python
tasks = [
    ("点击麦乐送", False),  # 简单任务，不需要反思
    ("点击鸡肉汉堡栏目", False),
    ("向下滑动找到板烧鸡腿堡", True),  # 需要多次滑动，启用反思
    ("加入购物车", True),
    ("点击结算", False)
]

for instruction, need_reflection in tasks:
    result = await executor.execute(
        instruction=instruction,
        enable_reflection=need_reflection,
        max_iterations=5 if need_reflection else 1
    )
```

---

## 🔍 反思结果说明

### action_result 含义

- **A (Successful)**: 完全成功，子目标已完成
  - 示例："找到板烧鸡腿堡" → 屏幕上已显示目标商品
  - 行为：退出循环

- **B (Partial Successful)**: 部分成功，需要继续
  - 示例："向下滑动找到X" → 已滑动但还没看到目标
  - 行为：继续循环

- **C (Failure - 需回退)**: 失败，结果错误
  - 示例：点击了错误的元素，进入了其他页面
  - 行为：可以尝试纠正或退出

- **D (Failure - 无变化)**: 失败，动作没有产生效果
  - 示例：滑动到底部无法继续滑动
  - 行为：可以尝试其他策略或退出

### progress_status

描述当前任务的进度状态，例如：
- "正在查找板烧鸡腿堡"
- "已找到板烧鸡腿堡"
- "已滑动到列表底部"

---

## 📊 输出结果

### ExecutionOutput 新增字段

```python
result = await executor.execute(...)

# 新增字段
result.iterations           # 执行的迭代次数
result.progress_info        # ProgressInfo 对象
    .action_result         # A/B/C/D
    .progress_status       # 进度描述
    .error_potential_causes  # 错误原因（如果失败）
```

### 完整示例

```python
result = await executor.execute(
    "向下滑动找到板烧鸡腿堡",
    enable_reflection=True,
    max_iterations=5
)

print(f"成功: {result.success}")
print(f"迭代次数: {result.iterations}")
print(f"总执行时间: {result.execution_time:.2f}秒")
print(f"执行的动作数: {len(result.actions_taken)}")

if result.progress_info:
    print(f"最终结果: {result.progress_info.action_result}")
    print(f"进度状态: {result.progress_info.progress_status}")
```

---

## ⚙️ 配置参数

### execute() 方法新增参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enable_reflection` | bool | `True` | 是否启用反思循环 |
| `max_iterations` | int | `5` | 最大循环次数 |

### 建议配置

- **简单任务**（点击按钮）：`enable_reflection=False`
- **可能需要多步的任务**（滑动查找）：`enable_reflection=True, max_iterations=5`
- **复杂任务**（多步操作）：`enable_reflection=True, max_iterations=10`

---

## 🎯 适用场景

### ✅ 推荐使用反思的场景

1. **滑动查找**：向下滑动找到某个元素
2. **多步操作**：需要连续执行多个相关动作
3. **等待加载**：等待页面加载完成后再操作
4. **搜索任务**：输入搜索词后等待结果

### ❌ 不推荐使用反思的场景

1. **单步操作**：点击一个明确的按钮
2. **确定性任务**：操作结果100%确定的任务
3. **已知单步完成**：通过分析确定一次就能完成

---

## 📝 注意事项

1. **API 调用次数**：启用反思会增加 LLM API 调用次数
   - 每次迭代：2次调用（决策 + 反思）
   - 建议根据任务复杂度设置合理的 `max_iterations`

2. **执行时间**：反思会增加执行时间
   - 每次反思需要额外的屏幕捕获和 LLM 调用
   - 对于时间敏感的任务，可以禁用反思

3. **循环终止**：
   - 达到 `max_iterations` 后会强制退出
   - 如果任务始终无法完成，检查 `action_result` 和错误信息

---

## 🔗 相关文件

- `Executor/executor.py` - 主执行器（第658-856行：反思相关方法）
- `Executor/output.py` - 输出结果类（新增字段）
- `integration/reflection_example.py` - 使用示例

---

## 🎓 与原始 Fairy 的对比

| 特性 | 原始 Fairy | FairyExecutor |
|------|-----------|---------------|
| 反思机制 | ✅ AppReflectorAgent | ✅ _reflect_on_execution |
| 消息传递 | Citlali EventMessage | ❌ 直接函数调用 |
| 内存管理 | ShortTimeMemoryManager | ❌ 简化版 |
| 全局规划 | GlobalPlannerAgent | ❌ 手动提供 plan_context |
| 可配置性 | 固定启用 | ✅ 可选启用/禁用 |

**总结**：提取了原始 Fairy 的反思核心逻辑，适配到简化的架构中。
