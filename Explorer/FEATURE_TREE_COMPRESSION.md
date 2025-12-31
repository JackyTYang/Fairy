# Feature Tree 压缩优化方案

## 问题背景

原始的 `feature_tree.json` 存在大量冗余：
- 每个 `PageState` 的 `path_from_root` 都包含完整的 `PathStep` 对象列表
- 同一个 step 可能在多个 state 的 `path_from_root` 中重复出现
- 导致文件体积过大，不适合直接作为 LLM prompt

## 优化方案

### 核心思想：引用去重

将 `PathStep` 对象集中存储在顶层 `steps` 字典中，`path_from_root` 只存储 `step_id` 引用。

### 数据结构对比

#### 原始结构（完整版）
```json
{
  "features": {...},
  "states": {
    "state_xxx": {
      "path_from_root": [
        {
          "step_id": "step_1",
          "instruction": "...",
          "actions": [...],
          "from_state_id": "...",
          "to_state_id": "...",
          ...
        },
        {
          "step_id": "step_2",
          ...
        }
      ]
    }
  }
}
```

#### 压缩版结构
```json
{
  "features": {...},
  "steps": {
    "step_1": {
      "step_id": "step_1",
      "instruction": "...",
      "actions": [...],
      "from_state_id": "...",
      "to_state_id": "...",
      ...
    },
    "step_2": {...}
  },
  "states": {
    "state_xxx": {
      "path_from_root": ["step_1", "step_2"]  // ⭐ 只存ID引用
    }
  }
}
```

## 压缩效果

### 测试数据（20251229_162639探索结果）

- **原始大小**: 74.8KB (1947行)
- **压缩后大小**: 29.7KB
- **压缩率**: **60.3%**
- **节省空间**: 45.2KB

### Step重复分析

- 唯一step数量: 15
- 总引用次数: 120
- 平均每个step被引用: **8.0次**
- 被引用最多的steps:
  * step_1: 15次（每个state的path都包含它）
  * step_2: 14次
  * step_3: 13次

## 实现细节

### 1. 实体类修改 (`entities.py`)

#### FeatureTree 添加 steps 字典
```python
@dataclass
class FeatureTree:
    root_feature_id: str
    features: Dict[str, FeatureNode] = field(default_factory=dict)
    states: Dict[str, PageState] = field(default_factory=dict)
    steps: Dict[str, PathStep] = field(default_factory=dict)  # ⭐ 新增
    state_transitions: List[tuple] = field(default_factory=list)
```

#### 新增压缩序列化方法
```python
def to_dict_compressed(self) -> Dict[str, Any]:
    """序列化为压缩版字典"""
    # 收集所有steps到steps字典（避免重复）
    all_steps = {}
    for state in self.states.values():
        for step in state.path_from_root:
            if step.step_id not in all_steps:
                all_steps[step.step_id] = step

    # states的path_from_root只存step_id列表
    compressed_states = {}
    for sid, state in self.states.items():
        state_dict = {
            ...
            'path_from_root': [step.step_id for step in state.path_from_root],  # ⭐
            ...
        }
        compressed_states[sid] = state_dict

    return {
        'features': ...,
        'states': compressed_states,
        'steps': {step_id: step.to_dict() for step_id, step in all_steps.items()},
        ...
    }
```

#### 新增压缩保存方法
```python
def save_to_file_compressed(self, filepath: Path):
    """保存功能树到文件（压缩版）"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(self.to_dict_compressed(), f, indent=2, ensure_ascii=False)
```

### 2. 自动保存压缩版 (`feature_tree_builder.py`)

修改 `save_tree` 方法，同时保存完整版和压缩版：

```python
def save_tree(self, filepath: Path):
    """保存功能树（同时保存完整版和压缩版）"""
    # 保存完整版
    self.tree.save_to_file(filepath)

    # 保存压缩版
    compressed_path = filepath.parent / f"{filepath.stem}_compressed{filepath.suffix}"
    self.tree.save_to_file_compressed(compressed_path)

    # 计算并显示压缩率
    ...
```

### 3. 工具函数 (`feature_tree_utils.py`)

提供压缩版的加载、查询、还原功能：

```python
def load_compressed_tree(compressed_path: Path) -> Dict[str, Any]:
    """加载压缩版feature_tree"""
    ...

def expand_compressed_tree(compressed_data: Dict[str, Any]) -> Dict[str, Any]:
    """将压缩版还原为完整版（需要时）"""
    # 从steps字典还原path_from_root中的step对象
    ...

def get_state_path(compressed_data: Dict[str, Any], state_id: str) -> List[Dict]:
    """获取到达某个state的完整路径（step序列）"""
    # 直接从steps字典查询，无需还原整个tree
    ...

def print_tree_summary(compressed_data: Dict[str, Any]):
    """打印feature_tree摘要信息"""
    ...
```

## 使用方式

### 1. 自动生成（Explorer运行时）

```python
# feature_tree_builder会自动在save_tree时生成两个文件：
# - feature_tree.json（完整版，保留所有信息）
# - feature_tree_compressed.json（压缩版，用于prompt）
```

### 2. 手动加载使用

```python
from feature_tree_utils import load_compressed_tree, get_state_path, print_tree_summary

# 加载压缩版
data = load_compressed_tree("feature_tree_compressed.json")

# 打印摘要
print_tree_summary(data)

# 查询某个state的路径
path = get_state_path(data, "state_main_xxx")

# 如果需要完整版（不推荐，会消耗内存）
full_data = expand_compressed_tree(data)
```

### 3. 喂给LLM作为prompt

压缩版可以直接序列化为JSON字符串，作为prompt的一部分：

```python
import json

# 加载压缩版
data = load_compressed_tree("feature_tree_compressed.json")

# 提取需要的部分（例如只要features和steps）
prompt_data = {
    'features': data['features'],
    'steps': data['steps']  # 集中存储的所有步骤
}

prompt = f"""
根据以下功能树信息...

{json.dumps(prompt_data, ensure_ascii=False, indent=2)}
"""
```

## 优势总结

1. **空间节省**：压缩率60%+，显著减少文件大小
2. **无损压缩**：可以完全还原为原始结构，无信息丢失
3. **查询高效**：需要某个step信息时，直接从steps字典查询，O(1)复杂度
4. **适合prompt**：体积更小，token消耗更少，更适合作为LLM的上下文
5. **向后兼容**：完整版仍然保存，不影响现有代码

## 文件清单

### 修改的文件
- `Explorer/entities.py`: FeatureTree添加steps字段和压缩方法
- `Explorer/feature_tree_builder.py`: save_tree同时保存压缩版

### 新增的文件
- `Explorer/feature_tree_utils.py`: 压缩版的加载、查询、还原工具
- `Explorer/test_compression.py`: 压缩效果测试脚本

### 输出文件
- `feature_tree.json`: 完整版（保留所有信息）
- `feature_tree_compressed.json`: 压缩版（用于prompt，60%体积）

## 注意事项

1. **两个版本都保留**：完整版用于调试和分析，压缩版用于prompt
2. **steps字典是全局的**：包含所有唯一的step对象
3. **path_from_root保持顺序**：step_id列表的顺序与原始step对象列表一致
4. **向后兼容**：现有读取完整版的代码不受影响