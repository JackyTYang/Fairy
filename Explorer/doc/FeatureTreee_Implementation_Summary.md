# 功能状态树实现总结

## 已完成的工作

### 1. 数据结构 (`entities.py`)

✅ **PathStep** - 探索路径步骤
- 记录从一个状态到另一个状态的转换
- 包含指令、动作、成功与否、时间戳等信息

✅ **PageState** - 页面状态
- 代表一个功能页面（State = 页面，不是操作）
- 存储双截图（immediate + stable）完整信息
- 记录从首页到当前状态的完整路径（path_from_root）
- 跟踪可达状态（reachable_states）

✅ **FeatureNode** - 功能节点
- 代表一个功能模块（根功能或子功能）
- 维护该功能包含的所有State ID列表
- 支持功能层次结构（parent/sub_features）

✅ **FeatureTree** - 功能状态树
- 管理整个探索过程中发现的功能和状态
- 快速索引（features、states字典）
- 记录状态转换关系（state_transitions）

✅ **ExplorationPlan** 扩展
- 添加 `feature_structure`: 功能结构（Initial Plan时输出）
- 添加 `current_feature`: 当前功能信息
- 添加 `feature_update`: 功能结构更新（Replan时动态调整）

### 2. State识别器 (`state_identifier.py`)

✅ **StateIdentifier** - 页面状态识别
- 基于 Activity + UI结构哈希 识别State
- 生成唯一的 state_id（格式：`state_<activity>_<hash>`）
- 过滤动态内容（数字、时间等）保证哈希稳定性
- 缓存已识别的State，避免重复识别

### 3. 功能树构建器 (`feature_tree_builder.py`)

✅ **FeatureTreeBuilder** - 构建和维护功能状态树
- 初始化根功能和子功能框架
- 添加State到功能树
- 支持动态功能更新：
  - `add_new`: 添加新发现的子功能
  - `rename`: 重命名功能
  - `split`: 拆分复杂功能
- 记录功能更新日志（feature_update_log）
- 保存功能树到JSON文件

### 4. Planner扩展 (`planner.py`)

✅ **Initial Plan Prompt 增强**
- 添加功能结构分析任务
- 要求LLM输出 `feature_structure` 和 `current_feature`
- 让LLM将探索任务分解为2-5个子功能

✅ **Replan Prompt 增强**
- 添加当前功能探索状态提示
- 添加功能状态判断任务（3个判断点）
- 要求LLM输出 `feature_update` 和 `current_feature`
- 支持动态发现和调整子功能

✅ **响应解析更新**
- 解析 `feature_structure`、`current_feature`、`feature_update` 字段
- 正确处理缺失字段（使用默认值）

### 5. Explorer集成 (`explorer.py`)

✅ **初始化阶段**
- 创建 StateIdentifier 实例
- 创建 FeatureTreeBuilder 实例（在初始计划后）
- 从初始计划中提取功能结构并初始化功能树
- 设置当前功能路径（current_feature_path）

✅ **执行循环**
- 每次步骤执行后：
  - 识别当前State（state_id）
  - 添加State到功能树（关联到当前功能路径）
  - 记录State转换关系

✅ **Replan阶段**
- 检查功能结构更新（feature_update）
- 应用更新到功能树
- 检测功能切换（feature_path变化）
- 更新当前功能路径

✅ **结束阶段**
- 保存功能树到 `feature_tree.json`
- 保存功能更新日志到 `feature_updates.json`
- 输出功能树摘要

## 输出文件结构

```
output/exploration/<session_id>/
  ├── feature_tree.json           # 完整的功能状态树
  ├── feature_updates.json        # 功能更新历史日志
  ├── initial_plan.json           # 初始计划（包含feature_structure）
  ├── plan_after_step_X.json      # 每次replan后的计划
  ├── final_plan.json             # 最终计划
  ├── exploration_result.json     # 探索结果摘要
  ├── step_1/                     # 每个步骤的详细信息
  │   ├── immediate/              # 0.2秒双截图
  │   │   ├── screenshot_XXX.jpeg
  │   │   ├── screenshot_XXX_marked.jpeg
  │   │   ├── ui_dump_XXX.xml
  │   │   ├── compressed_XXX.xml
  │   │   ├── compressed_XXX.txt
  │   │   └── som_mapping_XXX.json
  │   ├── stable/                 # 5秒双截图
  │   │   └── ... (同样的6个文件)
  │   ├── executor_result.json
  │   └── snapshot.json
  └── ...
```

## 核心工作流程

```
1. 用户启动探索
   └─> 指定 feature_to_explore = "点餐功能"

2. Initial Planning
   ├─> LLM分析首页
   ├─> 识别子功能: ["浏览菜单", "选择套餐", "加入购物车"]
   ├─> 生成初始计划
   └─> FeatureTreeBuilder初始化功能树

3. 执行循环 (每个step)
   ├─> Executor执行动作
   ├─> 捕获双截图（0.2s + 5s）
   ├─> StateIdentifier识别当前State
   ├─> FeatureTreeBuilder.add_state()
   │    ├─> 创建PageState（包含双截图、完整路径）
   │    └─> 归属到current_feature_path
   └─> 记录State转换

4. Replan阶段
   ├─> LLM分析当前页面
   ├─> 判断是否还在当前功能中
   ├─> 如果不在，识别新功能或功能切换
   ├─> 输出feature_update（add_new/rename/split/none）
   ├─> FeatureTreeBuilder.update_feature_structure()
   └─> Explorer更新current_feature_path

5. 探索结束
   ├─> 保存feature_tree.json
   ├─> 保存feature_updates.json
   └─> 输出功能树摘要
```

## 关键设计决策

### 1. State = 页面，不是操作
- State代表页面状态（如"点餐界面"、"套餐配品弹窗"）
- Transition代表操作（从State A到State B）

### 2. 双截图完整保存
- Immediate和Stable都有完整的6个文件
- 支持检测快速消失的toast/bubble提示

### 3. 完整路径存储
- 每个State的path_from_root记录从首页到达的所有步骤
- 确保路径可复现

### 4. LLM负责理解，本地代码负责记录
- LLM：识别功能、命名、判断功能状态、决定更新
- 本地代码：识别State、构建树、记录转换、保存数据

### 5. 动态功能调整
- Initial Plan只是初步预测
- Replan阶段可以add_new/rename/split功能
- 所有更新都记录在feature_updates.json中

## 使用示例

```python
from Explorer import FairyExplorer, ExplorerConfig, ExplorationTarget

# 配置
config = ExplorerConfig.from_env()

# 创建Explorer
explorer = FairyExplorer(config)

# 定义探索目标
target = ExplorationTarget(
    app_name="麦当劳",
    app_package="com.mcdonalds.gma.cn",
    app_description="麦当劳点餐应用",
    feature_to_explore="点餐功能",  # ← 根功能
    starting_state="首页"
)

# 执行探索
result = await explorer.explore(target)

# 查看功能树
import json
with open(result.output_dir + "/feature_tree.json") as f:
    tree = json.load(f)
    print(f"发现 {len(tree['features'])} 个功能")
    print(f"记录 {len(tree['states'])} 个状态")
    print(f"识别 {len(tree['state_transitions'])} 个转换")
```

## 后续优化方向

1. **让LLM命名State**
   - 当前State名称较简单（activity_page）
   - 可以让LLM根据页面内容生成更有意义的名称

2. **State相似度判断**
   - 当前基于UI结构哈希
   - 可以引入视觉相似度（截图对比）

3. **功能自动聚类**
   - 当发现大量State时，自动聚类为子功能
   - 辅助LLM进行功能识别

4. **路径优化**
   - 识别到达同一State的多条路径
   - 推荐最短路径

5. **可视化**
   - 生成功能树的可视化图表
   - 生成State转换图（状态机）

---

**实现状态**: ✅ 核心功能已全部实现，可以开始测试！

**作者**: Claude Code
**日期**: 2025-12-17
**版本**: v1.0
