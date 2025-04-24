import os
import xml.etree.ElementTree as ET
import re

# 布尔属性集合
BOOL_ATTRS = {
    "checkable", "checked", "clickable", "enabled", "focusable",
    "focused", "scrollable", "long-clickable", "password", "selected"
}
# 保留属性集合（不保留原始 bounds）
ATTRS = {
    "checkable", "checked", "clickable",
    "focused", "scrollable", "long-clickable", "password", "selected",
    "text", "class", "content-desc", "image-desc","visible-to-user"
}
# 可选保留/删除配置
KEEP_FALSE_BOOLEAN_ATTRS = {}
KEEP_EMPTY_STRING_ATTRS = {}
REMOVE_IF_TRUE_OR_NON_EMPTY = {}

# 预编译正则
VALLESS_RE = re.compile(r'\s+([\w-]+)="__VALLESS__"')


def merge_single_child_nodes(node):
    """合并只有一个子节点的层级，并向下传递属性和值"""
    for child in list(node):
        merged = merge_single_child_nodes(child)
        node.remove(child)
        node.append(merged)

    while len(node) == 1:
        child = node[0]
        for k, pv in node.attrib.items():
            cv = child.attrib.get(k, '')
            if k in BOOL_ATTRS:
                child.attrib[k] = 'true' if pv.lower() == 'true' or cv.lower() == 'true' else 'false'
            elif not cv.strip() and pv.strip():
                child.attrib[k] = pv
        parent_text = node.text.strip() if node.text and node.text.strip() else ''
        child_text = child.text.strip() if child.text and child.text.strip() else ''
        if parent_text:
            child.text = f"{parent_text} {child_text}".strip()
        node = child
    return node


# 新增：用于收集点击信息的列表
compress_info = []


def process_node(node, parent=None, keep_system_nav=False):
    """单次递归遍历，合并清理、重命名与中心点计算"""
    # 在清理前捕获原始 bounds
    raw_bounds = node.attrib.get('bounds')

    # 遍历子节点
    for child in list(node):
        process_node(child, node, keep_system_nav)

    # 删除系统导航栏节点
    if not keep_system_nav and node.attrib.get('package') == 'com.android.systemui':
        if parent is not None:
            parent.remove(node)
        return

    # 清理并重构属性字典
    new_attrib = {}
    clickable = False
    center = None

    for k, v in node.attrib.items():
        # 删除不在白名单的属性（原始 bounds 已不保留）
        if k not in ATTRS and k != 'bounds':
            continue
        val = v.strip()
        if k in BOOL_ATTRS:
            low = val.lower()
            if low == 'false' and k not in KEEP_FALSE_BOOLEAN_ATTRS:
                continue
            if (low == 'true' or val) and k in REMOVE_IF_TRUE_OR_NON_EMPTY:
                continue
            if low == 'true':
                new_attrib[k] = '__VALLESS__'
                if k == 'clickable':
                    clickable = True
                continue
        if k == 'bounds':
            # 不保留 bounds 原始属性
            continue
        if not val and k not in KEEP_EMPTY_STRING_ATTRS:
            continue
        new_attrib[k] = v
    node.attrib = new_attrib

    if raw_bounds:
        try:
            parts = raw_bounds.strip('[]').split('][')
            (x1, y1) = map(int, parts[0].split(','))
            (x2, y2) = map(int, parts[1].split(','))
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            center = f"[{cx},{cy}]"
        except Exception:
            pass
    # 仅在 clickable 为真且存在 raw_bounds 时添加 center
    if clickable:
        node.attrib['center'] = center

    # 收集 info
    text = node.attrib.get('text', '').strip()
    image_desc = node.attrib.get('image-desc', '').strip()
    if text:
        entry = {"text": f"text: {text}", "center": f"{center}"}
        if clickable:
            entry["clickable"] = True
        compress_info.append(entry)
    if image_desc:
        entry = {"text": f"icon: {image_desc}","center": f"{center}"}
        if clickable:
            entry["clickable"] = True
        compress_info.append(entry)

    # 根据 class 重命名标签
    cls = node.attrib.pop('class', None)
    if cls:
        node.tag = cls.split('.')[-1] if cls.startswith('android.') else cls

    # 删除无属性无子节点且文本空白节点
    if parent is not None and not node.attrib and not list(node) and not (node.text and node.text.strip()):
        parent.remove(node)


def tostring_with_valueless_true(node):
    xml_str = ET.tostring(node, encoding='unicode')
    return VALLESS_RE.sub(r' \1', xml_str)


def compressxml(input_path, output_path, keep_system_nav=False):
    global compress_info
    compress_info.clear()
    tree = ET.parse(input_path)
    root = tree.getroot()

    merged = merge_single_child_nodes(root)
    process_node(merged, None, keep_system_nav)

    compressed = tostring_with_valueless_true(merged)
    os.makedirs(output_path, exist_ok=True)
    outfile = os.path.join(output_path, os.path.basename(input_path))
    with open(outfile, 'w', encoding='utf-8') as f:
        f.write(compressed)
    print(f"✅ 压缩完成，结果保存于: {outfile}")
    return compress_info


def get_compress_xml(ui_hierarchy_xml, keep_system_nav=False):
    global compress_info
    compress_info.clear()
    root = ET.fromstring(ui_hierarchy_xml)
    merged = merge_single_child_nodes(root)
    process_node(merged, None, keep_system_nav)
    return tostring_with_valueless_true(merged), compress_info


def parse_bounds(bounds_str):
    try:
        parts = bounds_str.strip("[]").split("][")
        (x1, y1) = map(int, parts[0].split(","))
        (x2, y2) = map(int, parts[1].split(","))
        return x1, y1, x2, y2
    except Exception:
        return 0, 0, 0, 0
# 键盘激活检测保持原有逻辑


def is_keyboard_active(ui_xml, height, imes=None):
    imes = imes or [
        'com.google.android.inputmethod', 'com.sohu.inputmethod', 'com.baidu.input',
        'com.huawei.ime', 'com.nolan.inputmethod', 'com.iflytek.inputmethod',
        'com.tencent.qqpinyin'
    ]
    try:
        root = ET.fromstring(ui_xml)
    except:
        return False
    for node in root.iter():
        rid = node.attrib.get('resource-id', '')
        cls = node.attrib.get('class', '')
        vis = node.attrib.get('visible-to-user', 'false') == 'true'
        bounds = node.attrib.get('bounds', '')
        _, _, _, y2 = parse_bounds(bounds)
        if vis and (rid.startswith(tuple(imes)) or rid in ['android:id/input_method_nav_buttons',
                                                           'com.github.uiautomator:id/keyboard'] or 'keyboard' in cls.lower() or 'ime' in cls.lower()):
            if y2 >= height * 0.85:
                return True
    return False


if __name__ == '__main__':
    info = compressxml('window_dump-cleaned.xml', '../out')
    print(info)
