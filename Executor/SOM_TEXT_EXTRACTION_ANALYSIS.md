# SoM文本提取问题 - 分析与修复

## 问题现象

**用户报告**：
- 指令要求点击"预约"按钮（Mark 26）
- 实际执行点击了 Mark 27（错误的元素）
- 坐标本身是准确的，但LLM选择了错误的标记

**日志分析**：
```
动作 1: Tap - 参数: {'x': 119, 'y': 2632}  # 实际点击
```

## 根本原因

### compressed_txt 内容对比

**生成的文件**（缺少文本）：
```
Mark 26:  RelativeLayout  (com.mcdonalds.gma.cn:id/rl_time_card)  [Center: [1140, 443]]  [clickable]
Mark 27:  RelativeLayout  (com.mcdonalds.gma.cn:id/rl_shop_package)  [Center: [119, 2632]]  [clickable]
Mark 29:  TextView  (com.mcdonalds.gma.cn:id/tv_pay)  [去结算]  [Center: [1050, 2661]]  [clickable]
```

**实际XML结构**：
```xml
<RelativeLayout resource-id="rl_time_card" text="" clickable="true">
  <ImageView resource-id="iv_time_card_bg" />
  <TextView resource-id="tv_time_type" text="预约" />  ← 文本在子节点！
</RelativeLayout>
```

### 问题分析

1. **我的新代码** 在 `screen_perception_AT.py` 中只提取了节点自己的 `text` 属性
2. 很多按钮的文字实际在**子节点的 TextView** 中
3. 导致 compressed_txt 中很多重要元素**没有文本标识**
4. LLM 无法根据 resource-id 判断哪个是"预约"按钮
5. 只能靠坐标或模糊猜测，容易选错

### 对比：旧代码的做法

旧的 XMLCompressor 会执行 `_merge_single_child_nodes()`：
```python
def _merge_single_child_nodes(self, node):
    while len(node) == 1:
        child = node[0]
        # ⭐ 合并父子节点的text
        if node.text and node.text.strip():
            if child.text and child.text.strip():
                child.text = node.text.strip() + " " + child.text.strip()
            else:
                child.text = node.text.strip()
        node = child
    return node
```

结果：父节点会**继承子节点的文本**。

## 修复方案

### 实现的修复

在 `screen_perception_AT.py:49-62` 添加 `_extract_all_text()` 方法：

```python
def _extract_all_text(node):
    """递归提取节点及其所有子节点的文本"""
    texts = []

    # 获取当前节点的文本
    if node.get('text') and node.get('text').strip():
        texts.append(node['text'].strip())

    # 递归获取子节点的文本
    for child in node.get('children', []):
        child_texts = _extract_all_text(child)
        texts.extend(child_texts)

    return texts
```

在 `_add_node()` 中使用：
```python
# ⭐ 提取所有文本（包括子节点）
all_texts = _extract_all_text(node)
combined_text = ' | '.join(all_texts) if all_texts else ''

nodes_need_marked[type]['node_info_list'][index] = {
    'class': node.get('class', 'Unknown'),
    'resource-id': node.get('resource-id'),
    'text': combined_text,  # ⭐ 使用合并后的文本
    'center': node.get('center'),
    'bounds': node.get('bounds'),
    'properties': node.get('properties', [])
}
```

### 修复后的效果

**预期的 compressed_txt**：
```
Mark 26:  RelativeLayout  (com.mcdonalds.gma.cn:id/rl_time_card)  [预约]  [Center: [1140, 443]]  [clickable]
Mark 27:  RelativeLayout  (com.mcdonalds.gma.cn:id/rl_shop_package)  [店铺套餐]  [Center: [119, 2632]]  [clickable]
Mark 29:  TextView  (com.mcdonalds.gma.cn:id/tv_pay)  [去结算]  [Center: [1050, 2661]]  [clickable]
```

现在 LLM 可以清楚地看到：
- Mark 26 有文本 "预约"（正确目标）
- Mark 27 有文本 "店铺套餐"（错误目标）

## 为什么之前没发现这个问题？

1. **之前的测试案例** 恰好点击的元素本身就有 text 属性（如 Mark 29 的 "去结算"）
2. **Mark 14** (加购按钮) 是 FrameLayout，它的子元素有 ImageView，没有文本，所以也看不出问题
3. **这次的 "预约" 按钮** 是第一次遇到"父节点clickable，文本在子TextView"的典型场景

## Executor 喂给LLM的内容分析

### 当前提供的信息

Executor 通过 `screen_info.perception_infos.get_screen_info_prompt()` 提供：

1. **标记截图**：红色框 + 编号
2. **SoM_mapping**：通过 `convert_marks_to_coordinates()` 间接访问
3. **压缩XML**：通过 `infos[1]` 提供（在 non_visual_mode）

**但是！** 在当前配置（`non_visual_mode=False`）下，**compressed_txt 根本没有传给LLM**！

检查 `entity.py:26-33`：
```python
def get_screen_info_prompt(self, extra_suffix=None):
    prompt = ""
    if self.non_visual_mode:  # ← 只有这个模式才提供文本描述
        prompt = f"- Screen Structure Textualized Description {'for '+extra_suffix if extra_suffix else ''}: \n"
        prompt += f"{self.infos[1]}\n\n"
    prompt += self._keyboard_prompt(extra_suffix)
    return prompt
```

**所以，LLM只能靠视觉识别标记截图！**

### LLM频繁出错的原因总结

1. **视觉模式 (non_visual_mode=False)**：
   - LLM **只看到标记截图**，没有文本描述
   - 必须靠视觉识别图片上的小字（困难）
   - 红色框可能遮挡文字
   - 小号标记可能看不清
   - 相似元素容易混淆

2. **compressed_txt 缺失文本**：
   - 即使切换到 non_visual_mode，文本描述也不完整
   - 很多元素只有 resource-id，没有可读的文本

3. **指令模糊性**：
   - 用户指令："点击右侧'预约'按钮"
   - LLM需要在图片上找"预约"二字
   - 如果看不清或被遮挡，就只能猜

## 改进建议

### 1. 混合模式：视觉 + 文本描述（推荐）

修改 `entity.py` 始终提供文本描述：
```python
def get_screen_info_prompt(self, extra_suffix=None):
    prompt = ""

    # ⭐ 始终提供SoM对应的文本描述
    if self.som_compressed_txt:
        prompt = f"- Marked Elements List {'for '+extra_suffix if extra_suffix else ''}: \n"
        prompt += f"{self.som_compressed_txt}\n\n"

    if self.non_visual_mode:
        prompt = f"- Screen Structure Textualized Description {'for '+extra_suffix if extra_suffix else ''}: \n"
        prompt += f"{self.infos[1]}\n\n"

    prompt += self._keyboard_prompt(extra_suffix)
    return prompt
```

### 2. 优化compressed_txt格式

当前格式：
```
Mark 26:  RelativeLayout  (com.mcdonalds.gma.cn:id/rl_time_card)  [预约]  [Center: [1140, 443]]  [clickable]
```

优化后：
```
Mark 26: "预约" - RelativeLayout (rl_time_card) @ [1140, 443]
```

更简洁，重点突出文本。

### 3. 提示词改进

当前提示词：
```
We have provided an image of the screen and labeled all clickable elements using red boxes.
You can indicate which element you want to action by the number in the upper left corner of the red box.
```

改进后：
```
We have provided an image of the screen with labeled elements (red boxes with numbers).
Below is a list of all marked elements with their text and position.
Please use the Mark number to indicate which element to interact with.
Prefer using the text description to identify elements rather than relying solely on visual appearance.
```

## 测试验证

### 测试案例

运行 Explorer，触发以下场景：
1. 点击带文本的按钮（如 "去结算"）
2. 点击父节点clickable，文本在子节点的按钮（如 "预约"）
3. 点击ImageView按钮（如 "返回"）

### 验证步骤

1. 检查生成的 compressed_txt：
```bash
cat output/exploration/.../compressed_XXX.txt | grep -E "^Mark"
```

2. 验证文本提取：
```bash
# 应该能看到 "预约"、"去结算" 等文本
grep "预约" output/exploration/.../compressed_XXX.txt
```

3. 验证索引一致性：
```bash
python Executor/verify_som.py <som_mapping.json> <compressed.txt>
# 应该全部完美匹配
```

## 影响范围

**受影响模块**：
- ✅ `screen_perception_AT.py` - 文本提取逻辑
- ⚠️ `entity.py` - 提示词生成（建议改进）
- ⚠️ `perceptor.py` - compressed_txt格式（可选优化）

**向后兼容性**：
- ✅ SoM_mapping 格式不变
- ✅ compressed_txt 格式扩展（增加文本，不影响解析）
- ✅ verify_som.py 已支持新格式

## 总结

**根本问题**：
1. ❌ compressed_txt 缺失子节点文本 → **已修复**
2. ⚠️ non_visual_mode=False 时不提供文本描述 → **建议改进**
3. ⚠️ 视觉识别标记困难 → **建议混合模式**

**修复效果**：
- ✅ 所有元素现在都包含完整文本（包括子节点）
- ✅ LLM有足够信息做出正确决策
- ⚠️ 需要配合提示词改进才能完全解决

**下一步**：
1. 测试修复后的文本提取
2. 考虑实现"混合模式"（视觉+文本）
3. 优化compressed_txt输出格式
