# 功能状态树数据结构设计文档

## 1. 设计目标

在Explorer探索过程中构建**功能状态树**，用于：
- **记录功能结构**：应用的功能层次（如"点餐功能"包含"选择套餐"、"选择配菜"等子功能）
- **记录页面状态**：每个功能包含的所有页面状态（State = 页面，不是操作）
- **记录探索路径**：从首页到每个状态的完整可复现路径
- **支持回溯和多路径**：同一个状态可能有多条到达路径
- **为后续测试生成提供基础**：测试用例、测试计划、Oracle验证都依赖这个树

## 2. 核心概念定义

### 2.1 State（状态）= 页面
- **State 不是操作**，而是应用的一个**功能页面**
- 例如："首页"、"点餐界面"、"选择套餐弹窗"、"支付确认页"
- 识别方式：Activity名称 + UI结构哈希（相同Activity的不同页面状态）

### 2.2 Transition（转换）= 操作
- 从一个State到另一个State的**转换过程**
- 包含：执行的指令、动作序列、成功与否
- 例如：从"首页" --[点击点餐按钮]--> "点餐界面"

### 2.3 Path（路径）= 从首页到当前State的步骤链
- 每个State都记录**从首页到达它的完整路径**（步骤链）
- 支持多路径：同一个State可能通过不同路径到达
- 例如："首页" -> "点餐界面" -> "选择套餐" -> "选择配菜弹窗"

### 2.4 Feature（功能）= 功能模块
- 应用的功能层次结构
- 例如："点餐功能"包含多个子功能和多个页面状态
- 支持嵌套：根功能 -> 子功能 -> 孙功能

## 3. 数据结构设计

### 3.1 PathStep（路径步骤）
```json
{
  "step_id": "step_5",
  "instruction": "点击雪碧大杯标签",
  "actions": [{"name": "Tap", "arguments": {"x": 100, "y": 200}}],
  "from_state_id": "state_order_page_abc123",
  "to_state_id": "state_order_page_def456",
  "from_state_name": "选择套餐弹窗",
  "to_state_name": "选择套餐弹窗（饮料类）",
  "success": true,
  "timestamp": "2025-12-17 15:39:56"
}
```

**设计要点**：
- 记录从哪个状态到哪个状态（from/to）
- 包含状态ID（用于查找）和状态名称（用于可读性）
- 记录执行的动作和是否成功

### 3.2 PageState（页面状态）
```json
{
  "state_id": "state_order_page_def456",
  "state_name": "选择套餐弹窗（饮料类）",
  "activity_name": "com.mcdonalds.gma.cn.activity.MainActivity",

  "immediate_perception": {
    "screenshot_path": "step_5/immediate/screenshot_XXX.jpeg",
    "marked_screenshot_path": "step_5/immediate/screenshot_XXX_marked.jpeg",
    "xml_path": "step_5/immediate/ui_dump_XXX.xml",
    "compressed_xml_path": "step_5/immediate/compressed_XXX.xml",
    "compressed_txt_path": "step_5/immediate/compressed_XXX.txt",
    "som_mapping_path": "step_5/immediate/som_mapping_XXX.json",
    "timestamp": "1765957190"
  },

  "stable_perception": {
    "screenshot_path": "step_5/stable/screenshot_XXX.jpeg",
    "marked_screenshot_path": "step_5/stable/screenshot_XXX_marked.jpeg",
    "xml_path": "step_5/stable/ui_dump_XXX.xml",
    "compressed_xml_path": "step_5/stable/compressed_XXX.xml",
    "compressed_txt_path": "step_5/stable/compressed_XXX.txt",
    "som_mapping_path": "step_5/stable/som_mapping_XXX.json",
    "timestamp": "1765957195"
  },

  "path_from_root": [
    {"step_id": "step_1", "from": "首页", "to": "点餐界面", ...},
    {"step_id": "step_3", "from": "点餐界面", "to": "选择套餐弹窗", ...},
    {"step_id": "step_5", "from": "选择套餐弹窗", "to": "选择套餐弹窗（饮料类）", ...}
  ],

  "discovered_at": "2025-12-17 15:39:56",
  "reachable_states": ["state_order_page_xyz789", "state_payment_abc123"]
}
```

**设计要点**：
- **双截图完整存储**：immediate和stable都有完整的6个文件
- **完整路径**：`path_from_root` 记录从首页到当前状态的所有步骤（可复现）
- **可达状态**：记录从此状态可以到达哪些其他状态（用于生成状态图）
- **State ID生成规则**：`state_<activity_short_name>_<ui_structure_hash>`

### 3.3 FeatureNode（功能节点）
```json
{
  "feature_id": "feature_order",
  "feature_name": "点餐功能",
  "feature_description": "用户选择商品、套餐、配菜并加入购物车",
  "parent_feature_id": null,

  "states": [
    {PageState对象 - 点餐界面},
    {PageState对象 - 选择套餐弹窗},
    {PageState对象 - 选择套餐弹窗（饮料类）},
    {PageState对象 - 选择套餐弹窗（配菜类）}
  ],

  "sub_features": [
    {
      "feature_id": "feature_order_combo",
      "feature_name": "选择套餐配品",
      "feature_description": "在套餐弹窗中切换和选择配品",
      "parent_feature_id": "feature_order",
      "states": [...],
      "sub_features": []
    }
  ],

  "entry_state_id": "state_order_page_abc123"
}
```

**设计要点**：
- **功能层次**：通过 `parent_feature_id` 和 `sub_features` 构建树形结构
- **包含状态列表**：该功能相关的所有页面状态
- **入口状态**：从哪个状态进入这个功能

### 3.4 FeatureTree（功能状态树）
```json
{
  "root_feature": {FeatureNode对象 - 根功能},

  "state_index": {
    "state_order_page_abc123": {PageState对象},
    "state_order_page_def456": {PageState对象},
    ...
  },

  "feature_index": {
    "feature_order": {FeatureNode对象},
    "feature_order_combo": {FeatureNode对象},
    ...
  },

  "state_transitions": [
    {"from": "state_home", "to": "state_order_page_abc123", "step": "step_1"},
    {"from": "state_order_page_abc123", "to": "state_order_page_def456", "step": "step_5"},
    ...
  ]
}
```

**设计要点**：
- **根功能**：整个探索的根节点（如"麦当劳点餐功能"）
- **快速索引**：通过state_id或feature_id快速查找对应对象
- **状态转换图**：记录所有状态之间的转换关系

## 4. 与现有代码的整合

### 4.1 现有结构复用
- **PerceptionOutput**：已包含immediate和stable的完整双截图信息，直接复用
- **ExecutionSnapshot**：已记录每一步的完整信息，可转换为PathStep
- **StateTracker**：已保存immediate/和stable/子目录，可直接引用

### 4.2 新增模块建议
```
Explorer/
  ├── entities.py          # 添加：PathStep, PageState, FeatureNode, FeatureTree
  ├── state_tracker.py     # 现有：保存执行快照
  ├── feature_tree_builder.py  # 新增：构建功能树
  └── state_identifier.py  # 新增：识别页面状态（Activity + UI哈希）
```

### 4.3 构建流程
```
每执行一步 (execute step_i):
  ├─> Executor返回screen_after（包含双截图）
  ├─> StateIdentifier识别当前页面状态
  │     - 生成state_id（基于Activity + UI结构哈希）
  │     - 判断是否是新状态
  ├─> 如果是新状态:
  │     - 创建PageState对象
  │     - 保存immediate_perception和stable_perception
  │     - 记录path_from_root（当前路径的副本）
  │     - 添加到FeatureTree
  ├─> 记录状态转换
  │     - 创建PathStep对象（from_state -> to_state）
  │     - 添加到FeatureTree.state_transitions
  └─> 更新当前路径（用于下一步）
```

## 5. 输出示例

### 5.1 探索麦当劳点餐功能的最终树结构
```json
{
  "root_feature": {
    "feature_id": "feature_mcdonalds_order",
    "feature_name": "麦当劳点餐功能",
    "feature_description": "探索麦当劳应用的完整点餐流程",

    "states": [
      {
        "state_id": "state_home",
        "state_name": "首页",
        "path_from_root": [],
        "immediate_perception": {...},
        "stable_perception": {...}
      }
    ],

    "sub_features": [
      {
        "feature_id": "feature_browse_menu",
        "feature_name": "浏览菜单",
        "states": [
          {"state_id": "state_menu_list", "state_name": "菜单列表页", ...}
        ]
      },
      {
        "feature_id": "feature_order_combo",
        "feature_name": "选择套餐",
        "states": [
          {"state_id": "state_combo_popup", "state_name": "套餐配品弹窗", ...},
          {"state_id": "state_combo_drink", "state_name": "套餐饮料选择", ...},
          {"state_id": "state_combo_side", "state_name": "套餐配菜选择", ...}
        ]
      },
      {
        "feature_id": "feature_checkout",
        "feature_name": "结账支付",
        "states": [
          {"state_id": "state_cart", "state_name": "购物车", ...},
          {"state_id": "state_payment", "state_name": "支付确认页", ...}
        ]
      }
    ]
  }
}
```

### 5.2 可追溯路径示例
查询："如何到达'支付确认页'？"

返回：
```json
{
  "state_id": "state_payment",
  "state_name": "支付确认页",
  "path_from_root": [
    {
      "step_id": "step_1",
      "instruction": "点击首页的点餐按钮",
      "from_state_name": "首页",
      "to_state_name": "菜单列表页"
    },
    {
      "step_id": "step_3",
      "instruction": "点击麦辣鸡翅桶套餐",
      "from_state_name": "菜单列表页",
      "to_state_name": "套餐配品弹窗"
    },
    {
      "step_id": "step_8",
      "instruction": "点击确认选择",
      "from_state_name": "套餐配品弹窗",
      "to_state_name": "购物车"
    },
    {
      "step_id": "step_9",
      "instruction": "点击去结算",
      "from_state_name": "购物车",
      "to_state_name": "支付确认页"
    }
  ]
}
```

## 6. 使用场景

### 6.1 生成测试计划
- 遍历功能树，列出所有功能和状态
- 为每个功能生成测试用例模板

### 6.2 路径复现
- 根据 `path_from_root` 自动生成复现脚本
- 支持从任意状态开始测试

### 6.3 状态覆盖率
- 统计发现的状态数量
- 识别未探索的状态转换

### 6.4 Oracle生成
- 每个State的双截图可作为预期结果（Oracle）
- immediate截图用于检测toast/bubble提示

## 7. 关键设计决策

1. **State = 页面，不是操作**：避免混淆操作和状态的概念
2. **双截图完整保存**：immediate和stable都存储6个文件（原始/标记截图、XML、压缩XML、TXT、SoM mapping）
3. **完整路径存储**：每个State记录从首页到达的完整步骤链，确保可复现
4. **快速索引**：state_index和feature_index提供O(1)查找
5. **多路径支持**：同一个State可能有多条路径到达，都记录在path_from_root中

---

*本文档版本：v1.0*
*创建日期：2025-12-17*
*作者：Claude Code*
