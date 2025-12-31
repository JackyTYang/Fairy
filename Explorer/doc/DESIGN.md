# Explorer 模块设计总结

## ✅ 已完成的工作

### 1. 文件结构

```
Explorer/
├── __init__.py                 # 模块导出
├── config.py                   # 配置管理（从Explorer/.env加载）
├── entities.py                 # 数据实体定义
├── explorer.py                 # 核心Explorer类
├── planner.py                  # 计划管理器（使用LLM生成和重新规划）
├── perception_wrapper.py       # Perceptor封装（调用perception.py逻辑）
├── state_tracker.py            # 状态跟踪器（记录执行历史）
├── logger.py                   # 日志配置
├── .env.example                # 配置模板
└── README.md                   # 使用文档

integration/
└── explorer_example.py         # 使用示例
```

### 2. 核心功能

#### ✅ 配置管理 (config.py)
- [x] 从 `Explorer/.env` 加载配置
- [x] 支持 LLM 模型配置（独立于 Executor）
- [x] 支持视觉模型配置（用于 Perceptor）
- [x] 支持 ADB 配置
- [x] 可配置重新规划策略（`replan_on_every_step`）
- [x] 可配置最大步骤数限制

#### ✅ 数据实体 (entities.py)
- [x] `ExplorationTarget` - 输入：探索目标
- [x] `ExplorationStep` - 计划步骤
- [x] `ExplorationPlan` - 探索计划
- [x] `PerceptionOutput` - Perceptor输出
- [x] `ExecutionSnapshot` - 执行快照
- [x] `ExplorationResult` - 输出：探索结果
- [x] `NavigationState` - 导航状态（预留）

#### ✅ 屏幕感知封装 (perception_wrapper.py)
- [x] 封装 `perception.py` 的调用逻辑
- [x] 返回统一的 `PerceptionOutput` 对象
- [x] 包含所有6个输出文件路径
- [x] 支持非视觉模式（可选）

#### ✅ 计划管理器 (planner.py)
- [x] 使用独立的 LLM 配置
- [x] 初始计划生成（`create_initial_plan`）
- [x] 动态重新规划（`replan`）
- [x] LLM Prompt 设计
- [x] 响应解析

#### ✅ 状态跟踪器 (state_tracker.py)
- [x] 记录每一步的执行状态
- [x] 保存 Perceptor 输出文件
- [x] 保存 Executor 执行结果
- [x] 维护导航路径
- [x] 生成执行历史
- [x] 预留状态树接口

#### ✅ 核心Explorer (explorer.py)
- [x] 协调所有模块
- [x] 主探索流程（三阶段）
- [x] Executor 黑盒调用
- [x] 重新规划触发逻辑
- [x] 错误处理

#### ✅ 使用示例 (explorer_example.py)
- [x] 基础探索示例
- [x] 自定义探索示例
- [x] 结果查看代码

#### ✅ 文档
- [x] README.md - 完整使用文档
- [x] .env.example - 配置模板
- [x] 代码注释

---

## 🎯 设计要点

### 1. 模块化设计

每个模块职责清晰：
- **Explorer**: 主控制器
- **Planner**: 计划生成和重新规划
- **PerceptionWrapper**: 屏幕感知
- **StateTracker**: 状态记录
- **Executor**: 动作执行（黑盒）

### 2. 数据流向

```
ExplorationTarget (输入)
    ↓
[Perceptor] 捕获初始屏幕 → PerceptionOutput
    ↓
[Planner] 生成初始计划 → ExplorationPlan
    ↓
循环开始
    ├─ [Perceptor] 捕获当前屏幕 → PerceptionOutput
    ├─ [Planner] 获取下一步 → ExplorationStep
    ├─ [Executor] 执行动作 → ExecutionOutput
    ├─ [StateTracker] 记录状态 → ExecutionSnapshot
    └─ [Planner] 重新规划（如果需要） → ExplorationPlan
循环结束
    ↓
ExplorationResult (输出)
```

### 3. 与 Executor 的交互

**关键设计**：
- Explorer 使用**独立的 Perceptor** 进行屏幕感知
- Perceptor 的输出用于 **Planner 决策**，不传递给 Executor
- Executor 作为**黑盒**，有自己的屏幕感知和反思机制
- Explorer 只传递 `instruction` 和 `plan_context` 给 Executor
- Explorer 只关心 Executor 的 `ExecutionOutput` 结果

### 4. 重新规划策略

**每步重新规划**（已实现）：
```python
config.replan_on_every_step = True
```

原因：
- 没有应用知识库，不知道每个页面的功能
- 虽然每次规划多个步骤，但只执行第一个
- 执行后到达新页面，需要重新规划

可配置：
```python
config.replan_on_every_step = False
config.replan_interval = 3  # 每3步重新规划
```

### 5. 输出目录结构

```
output/exploration/YYYYMMDD_HHMMSS/
├── initial_plan.json               # 初始计划
├── final_plan.json                 # 最终计划
├── exploration_result.json         # 探索结果
├── navigation_path.json            # 导航路径
├── plan_after_step_X.json          # 重新规划后的计划
├── step_1/                         # 每个步骤的完整输出
│   ├── screenshot_xxx.png
│   ├── screenshot_xxx_marked.png
│   ├── raw_ui_xxx.xml
│   ├── ui_dump_xxx.xml
│   ├── ui_dump_xxx.txt
│   ├── som_mapping_xxx.json
│   ├── executor_result.json
│   └── snapshot.json
├── step_2/
└── ...
```

---

## 📋 核心接口

### 输入接口

```python
target = ExplorationTarget(
    app_name="应用名称",
    app_package="com.example.app",
    app_description="应用描述",
    feature_to_explore="要探索的功能",
    starting_state="首页"
)
```

### 输出接口

```python
result = await explorer.explore(target)

# 访问结果
result.success              # bool: 是否成功
result.total_steps          # int: 总步骤数
result.completed_steps      # int: 完成步骤数
result.failed_steps         # int: 失败步骤数
result.total_time           # float: 总耗时（秒）
result.output_dir           # str: 输出目录
result.execution_history    # List[ExecutionSnapshot]: 执行历史
result.final_plan           # ExplorationPlan: 最终计划
```

---

## 🔮 预留接口

为后续功能预留的接口：

1. **状态树构建**
   ```python
   state_tracker.save_state_tree()
   ```

2. **状态复原**
   ```python
   # TODO: 实现
   explorer.restore_state(state_id)
   ```

3. **父子步骤关系**
   ```python
   ExplorationStep(
       step_id="step_1_1",
       parent_step_id="step_1",
       ...
   )
   ```

---

## ⚙️ 配置说明

### Explorer 配置 (Explorer/.env)

```bash
# LLM配置（用于计划生成）
EXPLORER_LLM_MODEL_NAME=gpt-4o-2024-11-20
EXPLORER_LLM_API_KEY=sk-...
EXPLORER_LLM_API_BASE=https://api.openai.com/v1
EXPLORER_LLM_TEMPERATURE=0

# 视觉模型配置（用于Perceptor）
EXPLORER_VISUAL_MODEL_NAME=qwen-vl-plus
EXPLORER_VISUAL_API_KEY=sk-...
EXPLORER_VISUAL_API_BASE=https://...

# ADB配置
EXPLORER_ADB_PATH=/path/to/adb
EXPLORER_DEVICE_ID=  # 可选

# 执行配置
EXPLORER_MAX_EXPLORATION_STEPS=50
EXPLORER_REPLAN_ON_EVERY_STEP=true
EXPLORER_REPLAN_INTERVAL=1
EXPLORER_MAX_PLAN_STEPS=20
```

### Executor 配置 (Executor/.env)

Explorer 会自动加载 Executor 的配置，无需额外配置。

---

## 🚀 使用步骤

1. **配置环境**
   ```bash
   cd Explorer
   cp .env.example .env
   # 编辑 .env，填入API密钥
   ```

2. **连接设备**
   ```bash
   adb devices
   # 确保设备已连接
   ```

3. **运行示例**
   ```bash
   cd /path/to/Fairy
   python integration/explorer_example.py
   ```

4. **查看结果**
   - 控制台输出：实时日志
   - 文件输出：`output/exploration/YYYYMMDD_HHMMSS/`

---

## ✨ 设计亮点

1. **完全模块化**
   - 每个组件独立可测试
   - 配置集中管理
   - 接口清晰

2. **黑盒化 Executor**
   - Explorer 不依赖 Executor 内部实现
   - 只通过接口交互
   - 便于维护和升级

3. **独立的屏幕感知**
   - Explorer 有自己的 Perceptor
   - 用于计划决策
   - 不干扰 Executor 的感知

4. **灵活的重新规划**
   - 可配置触发策略
   - 支持每步规划或间隔规划
   - 适应不同场景

5. **完整的状态记录**
   - 每步保存所有文件
   - 构建完整执行历史
   - 便于调试和分析

6. **预留扩展空间**
   - 状态树构建
   - 状态复原
   - 知识库集成

---

## 📝 总结

Explorer 模块已经完成，实现了：
- ✅ 自动探索应用功能
- ✅ 动态生成和调整计划
- ✅ 完整的状态记录
- ✅ 模块化设计
- ✅ 灵活的配置
- ✅ 预留扩展接口

可以直接使用，也可以根据需要进一步扩展！
