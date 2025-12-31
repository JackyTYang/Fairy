# SoM标记错位问题 - 根本原因分析

## 问题现象

执行器(Executor)点击坐标不准确：
- LLM识别正确：应该点击"保存特制"按钮（标记"5"）
- 坐标错误：实际点击坐标 [1004, 748] 是"雪碧中杯"标签（标记"9"）
- 结果：点击失败，界面无变化

## 根本原因

### 问题1：SoM标记的独立生成流程

**三个独立的数据生成流程，没有同步：**

1. **视觉标记绘制** (`perceptor.py` line 40-51)
   - 使用 `draw_transparent_boxes_with_labels(boxes_dict=nodes_need_marked["clickable"]["node_bounds_list"])`
   - 红色框和标签编号直接从 `node_bounds_list` 的键值对中获取
   - 标记编号来自 `get_nodes_need_marked()` 的 `index` 变量

2. **SoM坐标映射** (`perceptor.py` line 36-38)
   ```python
   SoM_mapping = {}
   SoM_mapping.update(nodes_need_marked['clickable']['node_center_list'])  # ← 点击元素存储中心点
   SoM_mapping.update(nodes_need_marked['scrollable']['node_bounds_list'])  # ← 滚动区域存储边界
   ```
   - 使用与视觉标记**相同的索引**
   - clickable元素：存储 `center` 坐标
   - scrollable元素：存储 `bounds` 边界

3. **压缩文本生成** (`Perceptor/tools.py` line 183-186 + 195-238)
   ```python
   text_desc = self._format_ui_tree_to_text(compressed_root)
   ```
   - **完全独立**的遍历压缩后的XML树
   - 从XML的 `center` 属性读取坐标
   - **没有使用** `get_nodes_need_marked()` 的索引

### 问题2：元素遍历顺序不一致

**AccessibilityTree vs CompressedXML 的遍历顺序差异：**

- **`get_nodes_need_marked()`** (screen_perception_AT.py:34-62)
  - 使用 `_common_filter()` 递归遍历 `at_dict`
  - 先序遍历（parent → children）
  - 过滤条件：`"clickable" in node['properties']`

- **`_format_ui_tree_to_text()`** (Perceptor/tools.py:195-238)
  - 遍历 `ElementTree` 的压缩后XML
  - 先序遍历（parent → children）
  - **但XML已经经过压缩**：合并单子节点、删除无意义节点

**压缩后的XML结构已被修改**，元素顺序和数量都可能与原始AT不同！

### 问题3：标记索引与元素不对应

**实际测试数据验证：**

| SoM标记 | SoM_mapping坐标 | compressed_txt元素 | 实际中心坐标 | 距离 |
|---------|---------------|------------------|------------|------|
| 5 | [1154, 716] | TextView (保存特制) | [1154.0, 752.5] | 36.5px ❌ |
| 9 | [1004, 748] | TextView (雪碧中杯) | [1051.0, 748.5] | 47px ❌ |

**标记"5"应该对应"保存特制"，但坐标[1154, 716]距离实际中心[1154, 752]有36px偏差！**

## 代码路径追踪

### 1. SoM标记生成 (Fairy/tools/screen_perceptor/ssip_new/perceptor/perceptor.py:19-86)

```python
async def get_perception_infos(self, raw_screenshot_file_info, ui_hierarchy_xml, non_visual_mode, target_app, use_clickable_node_summaries):
    # 1. 解析 AccessibilityTree
    at = ScreenPerceptionAccessibilityTree(ui_hierarchy_xml, target_app=target_app)

    # 2. 获取需要标记的节点（同时设置 mark 属性）
    nodes_need_marked = at.get_nodes_need_marked(set_mark=True)  # ← 关键！

    # 3. 构建 SoM_mapping
    SoM_mapping = {}
    SoM_mapping.update(nodes_need_marked['clickable']['node_center_list'])
    SoM_mapping.update(nodes_need_marked['scrollable']['node_bounds_list'])

    # 4. 在截图上绘制红色框和标签
    screenshot_image_marked = draw_transparent_boxes_with_labels(
        screenshot_image,
        nodes_need_marked["clickable"]["node_bounds_list"],  # ← 使用 bounds 绘制框
        label_position="top_left",
        box_color=(255, 0, 0, 180)
    )

    return screenshot_file_info, SSIPInfo(..., SoM_mapping=SoM_mapping)
```

### 2. 节点标记索引分配 (screen_perception_AT.py:34-62)

```python
def get_nodes_need_marked(self, set_mark=False):
    index = 0
    nodes_need_marked = {
        "clickable": {'node_bounds_list':{}, 'node_center_list':{}},
        "scrollable": {'node_bounds_list': {}, 'node_center_list': {}}
    }

    def _add_node(node, type):
        nonlocal index
        if set_mark:
            node["mark"] = index  # ← 在AT节点上设置 mark 属性
        nodes_need_marked[type]['node_bounds_list'][index] = node["bounds"]
        nodes_need_marked[type]['node_center_list'][index] = node["center"]
        index = index + 1
        return node

    def _clickable_and_scrollable_filter(node):
        if "clickable" in node['properties']:
            node = _add_node(node, "clickable")
        elif "scrollable" in node['properties']:
            node = _add_node(node, "scrollable")
        return node

    # 遍历 at_dict（AccessibilityTree）
    self.at_dict = [self._common_filter(at_node, _clickable_and_scrollable_filter)
                    for at_node in self.at_dict]

    return nodes_need_marked
```

### 3. 压缩文本生成 (Perceptor/tools.py:183-238)

```python
async def compress_xml(self, ui_xml, timestamp, target_app=None):
    # 1. 解析 XML → ElementTree
    root = ET.fromstring(ui_xml)

    # 2. 压缩（合并单子节点、删除无意义节点）
    compressed_root = self._compress_xml_node(root)

    # 3. 转换为文本描述（**独立遍历压缩后的XML**）
    text_desc = self._format_ui_tree_to_text(compressed_root)

    return compressed_xml_path, text_path

def _format_ui_tree_to_text(self, node, indent=0):
    # 从压缩后的XML节点读取属性
    center = node.get('center', '')  # ← 从XML属性读取
    center_text = f"[Center: {center}]" if center else ""

    # 递归子节点
    for child in node:
        lines.append(self._format_ui_tree_to_text(child, indent + 1))

    return "\n".join(lines)
```

## 为什么会错位？

### 关键矛盾：

1. **`get_nodes_need_marked()`** 遍历的是 **原始 AccessibilityTree**
   - 结构：完整的UI层级
   - 顺序：先序遍历所有节点

2. **`_format_ui_tree_to_text()`** 遍历的是 **压缩后的 XML ElementTree**
   - 结构：已经过 `_merge_single_child_nodes()` 和 `_delete_meaningless_node()` 修改
   - 顺序：与原始AT可能完全不同
   - 节点数量：少于原始AT

3. **SoM_mapping 的索引** 来自 AccessibilityTree 遍历
   - 索引 `0, 1, 2, ...` 是按照 AT 的遍历顺序分配的

4. **compressed_txt 的元素** 来自 CompressedXML 遍历
   - 元素顺序：与压缩后的XML树结构对应
   - **与 AT 的遍历顺序不一致！**

### 具体示例：

假设原始UI有5个clickable元素：

**AccessibilityTree遍历顺序：**
```
index 0: RelativeLayout [clickable] → bounds + center
index 1: TextView "保存特制" [clickable] → bounds + center
index 2: ImageView [clickable] → bounds + center
index 3: TextView "选好了" [clickable] → bounds + center
index 4: TextView "雪碧中杯" [clickable] → bounds + center
```

**XML压缩后（合并单子节点）：**
```
<RelativeLayout clickable="true">  ← 与 TextView 合并了！
  <TextView text="选好了" clickable="true" />
  <TextView text="雪碧中杯" clickable="true" />
</RelativeLayout>
```

**CompressedXML 遍历顺序：**
```
element 0: RelativeLayout [clickable] + "保存特制"（合并后）
element 1: TextView "选好了" [clickable]
element 2: TextView "雪碧中杯" [clickable]
```

**结果：**
- SoM标记 index=1 本应指向 "保存特制"
- 但 compressed_txt 的第二个元素(index=1)是 "选好了"
- 坐标对应关系完全错乱！

## 验证方法

运行诊断脚本：
```bash
python verify_som.py step_6/stable/som_mapping_1766153824.json step_6/stable/compressed_1766153824.txt
```

## 修复方案

### 方案A：统一数据源（推荐）⭐

**核心思路**：让 compressed_txt 和 SoM_mapping 使用同一份数据。

1. **在 `get_nodes_need_marked()` 中记录完整元素信息**

修改 `screen_perception_AT.py`:
```python
def get_nodes_need_marked(self, set_mark=False):
    index = 0
    nodes_need_marked = {
        "clickable": {
            'node_bounds_list': {},
            'node_center_list': {},
            'node_info_list': {}  # ← 新增：存储完整节点信息
        },
        "scrollable": {
            'node_bounds_list': {},
            'node_center_list': {},
            'node_info_list': {}
        }
    }

    def _add_node(node, type):
        nonlocal index
        if set_mark: node["mark"] = index
        nodes_need_marked[type]['node_bounds_list'][index] = node["bounds"]
        nodes_need_marked[type]['node_center_list'][index] = node["center"]

        # ← 存储元素信息用于生成 compressed_txt
        nodes_need_marked[type]['node_info_list'][index] = {
            'class': node['class'],
            'resource-id': node.get('resource-id'),
            'text': node.get('text'),
            'center': node['center'],
            'bounds': node['bounds'],
            'properties': node['properties']
        }

        index = index + 1
        return node

    # ... 其余代码不变
    return nodes_need_marked
```

2. **使用同一份数据生成 compressed_txt**

修改 `perceptor.py`:
```python
async def get_perception_infos(self, ...):
    at = ScreenPerceptionAccessibilityTree(ui_hierarchy_xml, target_app=target_app)
    nodes_need_marked = at.get_nodes_need_marked(set_mark=True)

    # 构建 SoM_mapping
    SoM_mapping = {}
    SoM_mapping.update(nodes_need_marked['clickable']['node_center_list'])
    SoM_mapping.update(nodes_need_marked['scrollable']['node_bounds_list'])

    # ← 同时生成对应的元素描述文本（与SoM_mapping索引一致）
    compressed_txt = self._generate_compressed_txt_from_nodes(nodes_need_marked)

    # 绘制标记...

    return screenshot_file_info, SSIPInfo(..., SoM_mapping=SoM_mapping, compressed_txt=compressed_txt)

def _generate_compressed_txt_from_nodes(self, nodes_need_marked):
    """从标记节点信息生成 compressed_txt（确保索引一致）"""
    lines = []

    # Clickable 元素
    for idx in sorted(nodes_need_marked['clickable']['node_info_list'].keys()):
        info = nodes_need_marked['clickable']['node_info_list'][idx]
        line = f"- {info['class']} "
        if info['resource-id']:
            line += f"({info['resource-id']}) "
        if info['text']:
            line += f"[{info['text']}] "
        line += f"[Center: {info['center']}] "
        if info['properties']:
            line += f"[{', '.join(info['properties'])}]"
        lines.append(line)

    # Scrollable 元素
    for idx in sorted(nodes_need_marked['scrollable']['node_info_list'].keys()):
        info = nodes_need_marked['scrollable']['node_info_list'][idx]
        line = f"- {info['class']} [Bounds: {info['bounds']}] [scrollable]"
        lines.append(line)

    return "\n".join(lines)
```

### 方案B：在压缩后的XML中保留mark属性

**核心思路**：让压缩流程保留 mark 属性，确保XML中的mark与SoM_mapping对应。

1. **修改 `get_nodes_need_marked()` 使其在XML中设置mark**

问题：AT是从XML解析来的，但 `get_nodes_need_marked()` 只修改了AT对象，没有回写到XML。

这个方案需要在XML压缩前，将mark属性写回XML，工程量较大。

### 方案C：后处理校正SoM_mapping（临时方案）

**核心思路**：生成后对比 compressed_txt 和 SoM_mapping，自动校正映射关系。

```python
def align_som_mapping_with_compressed_txt(som_mapping, compressed_txt):
    """
    根据 compressed_txt 中的元素中心坐标，校正 SoM_mapping

    策略：
    1. 解析 compressed_txt 中所有元素的中心坐标
    2. 对于每个 SoM 标记，找到距离最近的元素
    3. 如果距离过大（>50px），警告可能的错误
    """
    # 解析 compressed_txt
    elements = []
    for line in compressed_txt.split('\n'):
        if '[Center: ' in line:
            # 提取中心坐标
            center_str = line.split('[Center: [')[1].split(']')[0]
            x, y = map(float, center_str.split(','))
            elements.append({'center': (int(x), int(y)), 'line': line})

    # 校正 SoM_mapping
    corrected_mapping = {}
    for mark, coord in som_mapping.items():
        if isinstance(coord[0], list):
            # 滚动区域，不校正
            corrected_mapping[mark] = coord
            continue

        # 找到最接近的元素
        min_dist = float('inf')
        best_match = None
        for elem in elements:
            dist = ((coord[0] - elem['center'][0])**2 + (coord[1] - elem['center'][1])**2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                best_match = elem

        if min_dist > 50:
            logger.warning(f"SoM标记 {mark} 与最近元素距离过大: {min_dist:.1f}px")

        corrected_mapping[mark] = best_match['center']

    return corrected_mapping
```

## 推荐修复方案

**短期（立即修复）：**
- 方案C：添加后处理校正逻辑

**长期（架构改进）：**
- 方案A：统一数据源，从根本上解决不一致问题

## 影响范围

**受影响模块：**
1. Executor - 坐标点击不准确
2. Explorer - 依赖Executor的点击准确性
3. Action Decider - LLM决策正确，但执行失败

**严重程度：** 🔴 高
- 直接导致任务执行失败
- 影响所有依赖SoM标记的操作
