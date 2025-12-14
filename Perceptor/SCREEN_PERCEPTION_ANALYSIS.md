# Fairy 屏幕感知模块详细分析

## 模块位置

```
Fairy/tools/screen_perceptor/
├── ssip_new/                          # SSIP (Screen Structured Info Perception) 主模块
│   ├── perceptor/                     # 感知器核心
│   │   ├── perceptor.py              # 主入口：ScreenStructuredInfoPerception
│   │   ├── screen_perception_AT.py   # 感知专用的AccessibilityTree
│   │   ├── entity.py                 # SSIPInfo数据结构
│   │   └── tools.py                  # 画框工具
│   ├── screen_AT.py                  # 基础AccessibilityTree解析
│   └── llm_tools/                    # LLM辅助工具
│       ├── visual_description_generator.py  # 图像描述生成
│       └── text_summarizer.py               # 文本摘要
└── fvp/                              # FVP (Full Visual Perception) 备选模块
```

## 核心类

### 1. ScreenStructuredInfoPerception (主入口)

**文件：** `Fairy/tools/screen_perceptor/ssip_new/perceptor/perceptor.py`

**作用：** 屏幕感知的主控制器

**初始化：**
```python
def __init__(self, visual_prompt_model_config, text_summarization_model_config):
    # 视觉描述生成器（用于non_visual_mode）
    self.image_description_generator = VisualDescriptionGenerator(visual_prompt_model_config)
    # 文本摘要器（用于总结可点击节点）
    self.text_summarizer = TextSummarizer(text_summarization_model_config)
```

**主要方法：**
```python
async def get_perception_infos(
    self,
    raw_screenshot_file_info,  # 原始截图
    ui_hierarchy_xml,          # UI层次结构XML
    non_visual_mode=False,     # 是否使用纯文本模式
    target_app=None,           # 目标应用包名
    use_clickable_node_summaries=True
):
```

## 完整工作流程

### 流程1: 视觉模式（Set-of-Marks，默认）

```
输入: 截图 + UI XML
    ↓
【步骤1】解析XML → AccessibilityTree
    ├─ 使用xmltodict解析XML为字典
    ├─ 过滤目标app的节点（排除系统UI）
    └─ 提取节点信息：class, bounds, text, properties等
    ↓
【步骤2】标记需要标注的节点
    ├─ 遍历所有节点，找到clickable和scrollable的节点
    ├─ 为每个节点分配唯一编号（从0开始递增）
    └─ 记录两种映射：
        - node_center_list: {编号 -> 中心点坐标}  # 用于Tap/LongPress
        - node_bounds_list: {编号 -> 边界坐标}    # 用于Swipe
    ↓
【步骤3】在截图上画框和标记
    ├─ 可点击元素：红色框，标签在左上角
    │   └─ draw_transparent_boxes_with_labels(
    │         box_color=(255, 0, 0, 180),
    │         label_position="top_left"
    │      )
    ├─ 可滚动元素：绿色框，标签在右上角，线宽5px
    │   └─ draw_transparent_boxes_with_labels(
    │         box_color=(0, 255, 0, 180),
    │         label_position="top_right",
    │         line_width=5
    │      )
    └─ 保存为 *_marked.jpeg
    ↓
输出: 标记后的截图 + SSIPInfo
    ├─ SoM_mapping: {编号 -> 坐标/边界}
    ├─ use_set_of_marks_mapping: True
    └─ non_visual_mode: False
```

### 流程2: 纯文本模式（non_visual_mode=True）

```
输入: 截图 + UI XML
    ↓
【步骤1】解析XML → AccessibilityTree
    （同流程1）
    ↓
【步骤2】为图像节点生成视觉描述
    ├─ 找到所有ImageView和View类型的叶子节点
    ├─ 使用视觉模型为每个图像生成文本描述
    │   └─ VisualDescriptionGenerator.generate_visual_description()
    │       └─ 调用LLM API（如qwen-vl-plus）
    └─ 将描述填充到节点的text字段
    ↓
【步骤3】总结可点击节点（可选）
    ├─ 找到所有clickable节点
    ├─ 收集每个节点的子节点内容
    ├─ 使用文本摘要模型生成简短描述
    │   └─ TextSummarizer.summarize_text()
    │       └─ 调用LLM API（如qwen-turbo）
    └─ 将摘要填充到节点的text字段
    ↓
【步骤4】生成页面文本描述
    ├─ 应用一系列过滤器：
    │   ├─ _coordinate_filter: 过滤坐标
    │   ├─ _redundant_info_filter: 移除冗余信息
    │   └─ _struct_compress: 结构压缩
    └─ 格式化为树形文本
    ↓
输出: 原始截图 + SSIPInfo
    ├─ SoM_mapping: None
    ├─ perception_infos: [ui_xml, page_description]
    └─ non_visual_mode: True
```

## 详细技术解析

### 1. XML解析和AccessibilityTree构建

**文件：** `screen_AT.py`

```python
class ScreenAccessibilityTree:
    def __init__(self, at_xml: str, target_app: None):
        # 使用xmltodict解析XML
        self.at_dict_raw = xmltodict.parse(self.at_xml_raw)['hierarchy']['node']

        # 过滤目标app的节点
        for at_node in self.at_dict_raw:
            if target_app is not None:
                if at_node['@package'] == target_app:
                    self.at_dict.append(self._node_info_collector(at_node, []))
```

**节点信息收集：**
```python
def _node_info_collector(self, at_node, layer):
    at_node_info = {}

    # 1. 基本信息
    at_node_info['class'] = at_node.get('@class')
    at_node_info['package'] = at_node.get('@package')
    at_node_info['resource-id'] = at_node.get('@resource-id')

    # 2. 属性（只收集非False的）
    at_node_info['properties'] = []
    for key, value in at_node.items():
        if value and value != 'false' and key in [
            '@checkable', '@checked', '@clickable', '@enabled',
            '@focusable', '@focused', '@scrollable', '@long-clickable',
            '@password', '@selected', '@visible-to-user'
        ]:
            at_node_info['properties'].append(key.replace('@', ''))

    # 3. 坐标解析
    # 输入: "[100,200][300,400]"
    # 输出: [[100, 200], [300, 400]]
    bounds = at_node.get('@bounds')
    pattern = r'\[(\d+),(\d+)\]'
    matches = re.findall(pattern, bounds)
    bounds = [[int(x), int(y)] for x, y in matches]

    # 4. 计算中心点
    at_node_info['center'] = [
        bounds[0][0] + ((bounds[1][0] - bounds[0][0]) // 2),
        bounds[0][1] + ((bounds[1][1] - bounds[0][1]) // 2)
    ]

    # 5. 文本信息
    at_node_info['text'] = at_node.get('@text', None).replace("\n","")

    # 6. 递归处理子节点
    at_node_info['children'] = []
    node = at_node.get('node', [])
    for sub_node in (node if isinstance(node, list) else [node]):
        at_node_info['children'].append(
            self._node_info_collector(sub_node, layer + [at_node_info['class']])
        )
```

### 2. Set-of-Marks标记生成

**文件：** `screen_perception_AT.py`

```python
def get_nodes_need_marked(self, set_mark=False):
    index = 0  # 全局编号计数器
    nodes_need_marked = {
        "clickable": {
            'node_bounds_list': {},  # {编号: [[x1,y1], [x2,y2]]}
            'node_center_list': {}   # {编号: [x, y]}
        },
        "scrollable": {
            'node_bounds_list': {},
            'node_center_list': {}
        }
    }

    def _add_node(node, type):
        nonlocal index
        if set_mark:
            node["mark"] = index  # 在节点上记录标记号

        # 记录边界和中心点
        nodes_need_marked[type]['node_bounds_list'][index] = node["bounds"]
        nodes_need_marked[type]['node_center_list'][index] = node["center"]

        index += 1
        return node

    def _clickable_and_scrollable_filter(node):
        if "clickable" in node['properties']:
            node = _add_node(node, "clickable")
        elif "scrollable" in node['properties']:
            node = _add_node(node, "scrollable")
        return node

    # 遍历所有节点
    self.at_dict = [
        self._common_filter(at_node, _clickable_and_scrollable_filter)
        for at_node in self.at_dict
    ]

    return nodes_need_marked
```

**返回的数据结构：**
```python
{
    "clickable": {
        'node_bounds_list': {
            0: [[100, 200], [300, 400]],
            1: [[350, 500], [500, 600]],
            ...
        },
        'node_center_list': {
            0: [200, 300],  # 中心点
            1: [425, 550],
            ...
        }
    },
    "scrollable": {
        'node_bounds_list': {
            10: [[0, 0], [1080, 1920]],
            ...
        },
        'node_center_list': {
            10: [540, 960],
            ...
        }
    }
}
```

### 3. 画框工具详解

**文件：** `tools.py`

```python
def draw_transparent_boxes_with_labels(
    image_input,              # PIL Image或numpy数组
    boxes_dict,               # {编号: [[x1,y1], [x2,y2]]}
    label_position='top_left',# 标签位置
    box_color=(255, 0, 0, 180),      # 框颜色（RGBA）
    text_color=(255, 255, 255, 255), # 文字颜色
    font_size=40,                     # 字体大小
    font_box_padding=10,              # 标签内边距
    font_box_background_color=(0, 0, 0, 160),  # 标签背景色
    line_width=10,                    # 线宽
    font_path=None,
):
```

**绘制过程：**

1. **转换为RGBA图像**
   ```python
   image = image_input.convert("RGBA")
   result = image.copy()
   ```

2. **遍历每个框**
   ```python
   for label, coords in boxes_dict.items():
       (x1, y1), (x2, y2) = coords
   ```

3. **计算标签位置**
   ```python
   text = str(label)  # 标记号
   text_bbox = temp_draw.textbbox((0, 0), text, font=font)
   text_width = text_bbox[2] - text_bbox[0]
   text_height = text_bbox[3] - text_bbox[1]

   if label_position == 'top_right':
       bg_x1 = x2 - text_width - font_box_padding * 2
       bg_x2 = x2
   elif label_position == 'top_left':
       bg_x1 = x1
       bg_x2 = x1 + text_width + font_box_padding * 2
   ```

4. **提取背景区域**
   ```python
   # 计算需要绘制的区域（包括框和标签）
   min_x = min(x1 - line_width, bg_x1)
   min_y = min(y1 - line_width, bg_y1)
   max_x = max(x2 + line_width, bg_x2)
   max_y = max(y2 + line_width, bg_y2)

   # 提取这个区域的背景
   background_crop = image.crop((min_x, min_y, max_x, max_y))
   ```

5. **创建透明叠加层**
   ```python
   overlay = Image.new("RGBA", background_crop.size, (0, 0, 0, 0))
   draw = ImageDraw.Draw(overlay)
   ```

6. **画框**
   ```python
   draw.rectangle(
       [x1 - min_x, y1 - min_y, x2 - min_x, y2 - min_y],
       outline=box_color,  # (255, 0, 0, 180) 红色半透明
       width=line_width     # 10像素宽
   )
   ```

7. **画标签背景**
   ```python
   draw.rectangle(
       [bg_x1 - min_x, bg_y1 - min_y, bg_x2 - min_x, bg_y2 - min_y],
       fill=font_box_background_color  # (255, 0, 0, 160) 红色背景
   )
   ```

8. **画文字**
   ```python
   text_x = bg_x1 - min_x + font_box_padding
   text_y = bg_y1 - min_y + font_box_padding
   draw.text((text_x, text_y), text, fill=text_color, font=font)
   ```

9. **合成回原图**
   ```python
   # 叠加层合成到背景裁剪
   composed_crop = Image.alpha_composite(background_crop, overlay)

   # 贴回结果图
   result.paste(composed_crop, (min_x, min_y))
   ```

**视觉效果：**
```
┌─────────────────────┐
│ 可点击元素（红框）     │
│ ┏━━━━━━━━━━━━━━━┓   │
│ ┃ [1] 按钮      ┃   │  ← 标签在左上角，红底白字
│ ┃               ┃   │
│ ┃    Click Me   ┃   │
│ ┃               ┃   │
│ ┗━━━━━━━━━━━━━━━┛   │
│                       │
│ 可滚动元素（绿框）     │
│ ┏━━━━━━━━━━━[10]┓   │  ← 标签在右上角，绿底白字
│ ┃               ┃   │
│ ┃   Scroll      ┃   │
│ ┃   List        ┃   │
│ ┗━━━━━━━━━━━━━━━┛   │
└─────────────────────┘
```

### 4. 结构压缩（Structure Compression）

**目的：** 减少冗余的嵌套层级，简化UI树

**文件：** `screen_perception_AT.py`

```python
def _struct_compress(self, node):
    def merge_info(parent, child):
        # 如果父子都可点击，不合并
        if 'center' in parent and 'center' in child:
            return parent

        # 如果只有父可点击，把坐标传给子
        elif 'center' in parent:
            child['bounds'] = parent['bounds']
            child['center'] = parent['center']

        # 合并父节点的属性到子节点
        for key in ['class', 'resource-id', 'properties']:
            if key in parent:
                child.setdefault(f'merged-{key}', [])
                if parent[key] not in child[f'merged-{key}']:
                    child[f'merged-{key}'].append(parent[key])

        return child

    # 如果只有一个子节点，则合并
    children = node.get('children', [])
    while len(children) == 1:
        child = children[0]
        child = merge_info(node, child)
        node = child
        children = node.get('children', [])

    # 递归压缩子节点
    if 'children' in node:
        node['children'] = [
            self._struct_compress(child)
            for child in node['children']
        ]

    return node
```

**压缩效果：**
```
压缩前:
LinearLayout (不可点击)
  └─ RelativeLayout (不可点击)
      └─ Button (可点击)
          └─ TextView
              └─ "Click"

压缩后:
Button (可点击)
  ├─ merged-class: ['LinearLayout', 'RelativeLayout']
  └─ TextView
      └─ "Click"
```

## 坐标映射机制

### SoM映射数据结构

```python
SoM_mapping = {
    # 可点击元素 → 中心点坐标
    0: [200, 300],       # 标记0 → (200, 300)
    1: [425, 550],       # 标记1 → (425, 550)
    2: [800, 200],       # 标记2 → (800, 200)

    # 可滚动元素 → 边界坐标
    10: [[0, 400], [1080, 1920]],    # 标记10 → 边界
    11: [[100, 500], [980, 1500]],   # 标记11 → 边界
}
```

### 坐标转换函数

**文件：** `ssip_new/perceptor/entity.py`

```python
def convert_marks_to_coordinates(self, mark_number):
    """将标记号转换为坐标"""
    if self.SoM_mapping is None:
        return None

    coords = self.SoM_mapping.get(mark_number)

    if coords is None:
        return None

    # 判断是中心点还是边界
    if isinstance(coords, list):
        if len(coords) == 2 and isinstance(coords[0], int):
            # 中心点: [x, y]
            return coords
        elif len(coords) == 2 and isinstance(coords[0], list):
            # 边界: [[x1, y1], [x2, y2]]
            return coords

    return None
```

### LLM返回的动作格式

**Tap动作（使用中心点）：**
```json
{
    "name": "Tap",
    "arguments": {
        "mark_number": 5
    }
}
```

**Swipe动作（使用边界）：**
```json
{
    "name": "Swipe",
    "arguments": {
        "mark_number": 10,
        "direction": "H",  // H=垂直, W=水平
        "distance": -1,    // 负数=向上/左，正数=向下/右
        "duration": 200
    }
}
```

## 使用示例

### 示例1: 基本使用（视觉模式）

```python
from Fairy.tools.screen_perceptor.ssip_new.perceptor.perceptor import ScreenStructuredInfoPerception
from Fairy.config.model_config import ModelConfig

# 1. 配置视觉模型
visual_model_config = ModelConfig(
    model_name="qwen-vl-plus",
    model_temperature=0,
    model_info={"vision": True, "function_calling": False, "json_output": False},
    api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key="sk-..."
)

# 2. 创建感知器
perceptor = ScreenStructuredInfoPerception(
    visual_prompt_model_config=visual_model_config,
    text_summarization_model_config=None  # 视觉模式不需要
)

# 3. 获取感知信息
screenshot_file_info, perception_infos = await perceptor.get_perception_infos(
    raw_screenshot_file_info=screenshot_file_info,
    ui_hierarchy_xml=ui_xml,
    non_visual_mode=False,  # 使用Set-of-Marks
    target_app="com.example.app"
)

# 4. 使用SoM映射
print(perception_infos.SoM_mapping)
# {0: [200, 300], 1: [425, 550], ...}

# 5. 转换标记号为坐标
coords = perception_infos.convert_marks_to_coordinates(5)
print(coords)  # [x, y] 或 [[x1, y1], [x2, y2]]
```

### 示例2: 纯文本模式

```python
# 1. 配置两个模型
visual_model_config = ModelConfig(...)  # 用于图像描述
text_model_config = ModelConfig(...)    # 用于文本摘要

# 2. 创建感知器
perceptor = ScreenStructuredInfoPerception(
    visual_prompt_model_config=visual_model_config,
    text_summarization_model_config=text_model_config
)

# 3. 获取感知信息
screenshot_file_info, perception_infos = await perceptor.get_perception_infos(
    raw_screenshot_file_info=screenshot_file_info,
    ui_hierarchy_xml=ui_xml,
    non_visual_mode=True,  # 纯文本模式
    target_app="com.example.app",
    use_clickable_node_summaries=True  # 启用节点摘要
)

# 4. 获取页面描述
page_description = perception_infos.perception_infos[1]
print(page_description)
# [
#   "LinearLayout\n  Button: '登录'\n  TextView: '忘记密码'",
#   ...
# ]
```

### 示例3: 在fairy_executor中使用

```python
from fairy_executor import ExecutorConfig, FairyExecutor

# 配置会自动创建ScreenStructuredInfoPerception
config = ExecutorConfig.from_env()

executor = FairyExecutor(config)

# 执行器内部会自动调用：
# screen_info = await self._get_screen_info()
#   └─ screenshot_file_info, perception_infos =
#       await self.screen_perceptor.get_perception_infos(...)
```

## 性能考虑

### 视觉模式（Set-of-Marks）

**优点：**
- ✅ 准确性高（LLM直接看到标记）
- ✅ 不需要复杂的文本描述

**缺点：**
- ⚠️ 需要画框和保存图像（~0.1-0.5秒）
- ⚠️ 图像文件大小增加
- ⚠️ LLM处理图像较慢

### 纯文本模式

**优点：**
- ✅ 不需要发送图像给LLM
- ✅ LLM处理速度快

**缺点：**
- ⚠️ 需要调用视觉模型生成图像描述（慢）
- ⚠️ 需要调用文本模型生成摘要（慢）
- ⚠️ 文本描述可能不如直接看图准确

### 性能对比

| 模式 | 初始化耗时 | LLM推理耗时 | 总耗时 | 准确性 |
|------|-----------|-----------|--------|--------|
| Set-of-Marks | 0.1-0.5秒 | 10-30秒 | 10-30秒 | ⭐⭐⭐⭐⭐ |
| 纯文本模式 | 5-15秒 | 5-10秒 | 10-25秒 | ⭐⭐⭐⭐ |

## 常见问题

### Q1: 为什么Swipe返回坐标而不是边界？

**原因：** 对于某些可滚动元素，系统可能只记录了中心点

**解决方案：**
- 在fairy_executor中已添加处理
- 如果返回的是坐标`[x, y]`，使用默认滑动距离（500像素）

### Q2: 如何查看标记后的图像？

**方法1：** 查看输出目录
```bash
output/会话ID/marked_images/exec_001_before_marked.jpg
```

**方法2：** 在代码中获取
```python
result = await executor.execute("点击按钮")
marked_image_path = result.output_files.get('marked_image_before')
```

### Q3: 如何调整标记样式？

修改 `perceptor.py` 中的参数：
```python
# 可点击元素
screenshot_image_marked = draw_transparent_boxes_with_labels(
    screenshot_image,
    nodes_need_marked["clickable"]["node_bounds_list"],
    label_position="top_left",
    box_color=(255, 0, 0, 180),      # 红色框
    font_box_background_color=(255, 0, 0, 160),  # 红色标签
    font_size=40,                     # 字体大小
    line_width=10                     # 线宽
)
```

## 总结

Fairy的屏幕感知模块是一个**高度模块化、功能完整**的系统：

1. **XML解析**：将Android UI层次结构转换为Python字典
2. **节点标记**：为可交互元素分配唯一编号
3. **可视化**：在截图上画框和标签（Set-of-Marks）
4. **坐标映射**：建立标记号到坐标的映射关系
5. **结构压缩**：简化UI树，减少冗余
6. **LLM集成**：支持视觉描述和文本摘要

这个设计使得LLM可以**准确地定位和操作UI元素**，而不需要直接处理像素坐标。
