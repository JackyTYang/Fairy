# Explorer 模块

Explorer 是 Fairy 的功能探索模块，用于自动探索 Android 应用的功能，生成探索计划并执行。

## 📦 模块结构

```
Explorer/
├── __init__.py                 # 模块导出
├── config.py                   # 配置管理
├── entities.py                 # 数据实体定义
├── explorer.py                 # 核心Explorer类
├── planner.py                  # 计划管理器
├── perception_wrapper.py       # 屏幕感知封装
├── state_tracker.py            # 状态跟踪器
├── logger.py                   # 日志配置
├── .env.example                # 配置模板
└── README.md                   # 本文档
```

## 🚀 快速开始

### 1. 配置环境变量

复制 `.env.example` 为 `.env` 并填入配置：

```bash
cd Explorer
cp .env.example .env
# 编辑 .env 文件，填入实际的 API 密钥和路径
```

必需的配置项：
- `EXPLORER_LLM_MODEL_NAME`: LLM模型名称（用于计划生成）
- `EXPLORER_LLM_API_KEY`: LLM API密钥
- `EXPLORER_LLM_API_BASE`: LLM API基础URL
- `EXPLORER_VISUAL_MODEL_NAME`: 视觉模型名称（用于屏幕感知）
- `EXPLORER_VISUAL_API_KEY`: 视觉模型API密钥
- `EXPLORER_VISUAL_API_BASE`: 视觉模型API基础URL
- `EXPLORER_ADB_PATH`: ADB可执行文件路径

### 2. 基本使用

```python
import asyncio
from Explorer import (
    ExplorerConfig,
    FairyExplorer,
    ExplorationTarget,
    setup_logger
)

async def main():
    # 配置日志
    setup_logger(log_level="INFO")

    # 加载配置
    config = ExplorerConfig.from_env()

    # 创建Explorer
    explorer = FairyExplorer(config)

    # 定义探索目标
    target = ExplorationTarget(
        app_name="麦当劳",
        app_package="com.mcdonalds.app",
        app_description="提供点餐、外卖、优惠券等功能",
        feature_to_explore="浏览菜单，找到鸡肉汉堡分类",
        starting_state="首页"
    )

    # 执行探索
    result = await explorer.explore(target)

    # 查看结果
    print(f"探索成功: {result.success}")
    print(f"完成步骤: {result.completed_steps}/{result.total_steps}")
    print(f"输出目录: {result.output_dir}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. 运行示例

```bash
cd /path/to/Fairy
python integration/explorer_example.py
```

## 📚 核心概念

### 输入：ExplorationTarget

定义要探索的应用和功能：

```python
target = ExplorationTarget(
    app_name="应用名称",
    app_package="com.example.app",
    app_description="应用的简短描述",
    feature_to_explore="要探索的功能描述",
    starting_state="首页"  # 起始状态
)
```

### 输出：ExplorationResult

包含探索的所有结果：

```python
result = await explorer.explore(target)

print(result.success)              # 是否成功
print(result.total_steps)          # 总步骤数
print(result.completed_steps)      # 完成的步骤数
print(result.failed_steps)         # 失败的步骤数
print(result.total_time)           # 总耗时（秒）
print(result.output_dir)           # 输出目录

# 执行历史
for snapshot in result.execution_history:
    print(snapshot.step_id)
    print(snapshot.executor_result)
    print(snapshot.navigation_path)
```

### 输出目录结构

```
output/exploration/YYYYMMDD_HHMMSS/
├── initial_plan.json               # 初始计划
├── final_plan.json                 # 最终计划
├── exploration_result.json         # 探索结果
├── navigation_path.json            # 导航路径
├── plan_after_step_X.json          # 每步重新规划后的计划
├── perceptor_temp/                 # Perceptor临时文件
├── step_1/                         # 步骤1的输出
│   ├── screenshot_xxx.png          # 原始截图
│   ├── screenshot_xxx_marked.png   # 标记截图
│   ├── raw_ui_xxx.xml              # 原始XML
│   ├── ui_dump_xxx.xml             # 压缩XML
│   ├── ui_dump_xxx.txt             # 压缩TXT
│   ├── som_mapping_xxx.json        # SoM映射
│   ├── executor_result.json        # Executor执行结果
│   └── snapshot.json               # 步骤快照
├── step_2/
│   └── ...
└── ...
```

## ⚙️ 配置说明

### 核心配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `max_exploration_steps` | 最大探索步骤数 | 50 |
| `replan_on_every_step` | 是否每步都重新规划 | true |
| `replan_interval` | 重新规划间隔 | 1 |
| `max_plan_steps` | 单次计划的最大步骤数 | 20 |

### 重新规划策略

Explorer 支持两种重新规划策略：

1. **每步重新规划**（推荐）：
   ```python
   config.replan_on_every_step = True
   ```
   - 每执行一步后都重新规划
   - 适用于没有应用知识库的场景
   - 能够根据页面变化动态调整计划

2. **间隔重新规划**：
   ```python
   config.replan_on_every_step = False
   config.replan_interval = 3  # 每3步重新规划
   ```
   - 按固定间隔重新规划
   - 减少LLM调用次数
   - 适用于有一定应用知识的场景

## 🔄 工作流程

```
1. 初始化
   ├─ 捕获初始屏幕（Perceptor）
   └─ 生成初始计划（Planner）

2. 执行循环
   ├─ 获取下一步
   ├─ 捕获当前屏幕（Perceptor）
   ├─ 执行动作（Executor - 黑盒）
   ├─ 记录状态（StateTracker）
   └─ 判断是否重新规划
       └─ 是 → 重新规划（Planner）

3. 结束
   ├─ 保存导航路径
   ├─ 保存最终计划
   └─ 生成探索结果
```

## 🔧 与 Executor 的交互

Explorer 将 Executor 作为**黑盒**使用：

```python
# Explorer 调用 Executor
executor_result = await self.executor.execute(
    instruction=step.instruction,
    plan_context={
        "overall_plan": current_plan.overall_plan,
        "current_sub_goal": step.sub_goal
    },
    enable_reflection=step.enable_reflection,
    max_iterations=step.max_iterations
)

# Executor 内部有自己的：
# - 屏幕感知
# - 反思机制（reflection）
# - 动作执行

# Explorer 只关心 Executor 的输出：
# - success: 是否成功
# - iterations: 迭代次数
# - actions_taken: 执行的动作
# - progress_info: 进度信息（A/B/C/D）
```

## 📊 日志

Explorer 使用 loguru 进行日志记录：

```python
# 配置日志
from Explorer import setup_logger

setup_logger(
    log_level="INFO",           # DEBUG/INFO/WARNING/ERROR
    log_file="explorer.log",    # 日志文件路径
    enable_console=True,        # 控制台输出
    enable_file=True            # 文件输出
)
```

## 🔮 预留接口

Explorer 为后续功能预留了扩展接口：

1. **状态树构建**：
   ```python
   state_tracker.save_state_tree()  # TODO: 实现状态树功能
   ```

2. **状态复原**：
   ```python
   # TODO: 实现状态保存和复原功能
   ```

3. **父子步骤关系**：
   ```python
   ExplorationStep(
       step_id="step_1",
       parent_step_id="step_0",  # 预留字段
       ...
   )
   ```

## ⚠️ 注意事项

1. **环境依赖**：
   - 需要先配置 Executor（Executor/.env）
   - 需要配置 Explorer（Explorer/.env）
   - 需要 ADB 连接到 Android 设备

2. **API 调用**：
   - 每次探索会调用多次 LLM API（计划生成 + 重新规划）
   - 每次屏幕感知会调用视觉模型 API
   - 建议设置合理的 `max_exploration_steps` 限制

3. **性能考虑**：
   - 每步都包含屏幕感知、LLM调用、动作执行
   - 完整探索可能需要较长时间
   - 可以通过调整 `replan_on_every_step` 优化性能

## 🐛 故障排查

1. **配置错误**：
   ```
   ValueError: 缺少必需的环境变量
   ```
   → 检查 Explorer/.env 文件是否正确配置

2. **Executor 初始化失败**：
   ```
   Error loading Executor config
   ```
   → 检查 Executor/.env 文件是否存在

3. **ADB 连接失败**：
   ```
   ADB device not found
   ```
   → 检查设备连接：`adb devices`

4. **LLM 调用失败**：
   ```
   API call failed
   ```
   → 检查 API 密钥和网络连接

## 📖 参考文档

- [Executor 文档](../Executor/README.md)
- [Perceptor 文档](../Perceptor/README.md)
- [使用示例](../integration/explorer_example.py)
