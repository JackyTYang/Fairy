import os
import xml.etree.ElementTree as ET

# 定义布尔属性列表
BOOL_ATTRS = {
    "checkable", "checked", "clickable", "enabled", "focusable",
    "focused", "scrollable", "long-clickable", "password", "selected"
}

# 配置：哪些布尔属性即使为 "false" 也保留
KEEP_FALSE_BOOLEAN_ATTRS = {"enabled"}  # 例如保留 "enabled", "focusable" 为 false 时的属性

# 配置：哪些非布尔属性为空时保留
KEEP_EMPTY_STRING_ATTRS = {"package"}  # 例如保留空的 "resource-id", "text" 等

# 配置：哪些属性即使为 "true" 或不为空也不保留
REMOVE_IF_TRUE_OR_NON_EMPTY = {"package"}  # 即使这些属性为 "true" 或非空，也不保留


def merge_attributes(parent_attrib, child_attrib):
    """
    合并父节点与子节点的属性（不删除 false，统一在后处理）。
    """
    merged = child_attrib.copy()
    for key, p_val in parent_attrib.items():
        if key in BOOL_ATTRS:
            c_val = child_attrib.get(key, "false")
            merged[key] = "true" if (p_val.lower() == "true" or c_val.lower() == "true") else "false"
        else:
            c_val = child_attrib.get(key, "")
            if not c_val.strip() and p_val.strip():
                merged[key] = p_val
    return merged


def merge_single_child_nodes(node):
    """
    合并仅包含单一子节点的结构，提升子节点。
    """
    children = list(node)
    for child in children:
        merged_child = merge_single_child_nodes(child)
        node.remove(child)
        node.append(merged_child)

    while len(node) == 1:
        child = node[0]
        child.attrib = merge_attributes(node.attrib, child.attrib)
        if node.text and node.text.strip():
            if child.text and child.text.strip():
                child.text = node.text.strip() + " " + child.text.strip()
            else:
                child.text = node.text.strip()
        node = child
    return node


def clean_false_attributes(node):
    """
    遍历所有节点，删除值为 false 且不在保留列表中的布尔属性。
    """
    keys_to_delete = [
        k for k, v in node.attrib.items()
        if k in BOOL_ATTRS and v.lower() == "false" and k not in KEEP_FALSE_BOOLEAN_ATTRS
    ]
    for k in keys_to_delete:
        del node.attrib[k]
    for child in node:
        clean_false_attributes(child)


def clean_empty_attributes(node):
    """
    遍历所有节点，删除值为空的属性（只删除空属性且不在保留列表中）。
    """
    keys_to_delete = [
        k for k, v in node.attrib.items()
        if not v.strip() and k not in KEEP_EMPTY_STRING_ATTRS
    ]
    for k in keys_to_delete:
        del node.attrib[k]
    for child in node:
        clean_empty_attributes(child)


def clean_remove_true_or_non_empty_attributes(node):
    """
    遍历所有节点，删除即使为 true 或非空的属性，如果在 REMOVE_IF_TRUE_OR_NON_EMPTY 配置项中。
    """
    keys_to_delete = [
        k for k, v in node.attrib.items()
        if k in REMOVE_IF_TRUE_OR_NON_EMPTY and (v.lower() == "true" or v.strip())
    ]
    for k in keys_to_delete:
        del node.attrib[k]
    for child in node:
        clean_remove_true_or_non_empty_attributes(child)


def compressxml(input_path, output_path):
    tree = ET.parse(input_path)
    root = tree.getroot()

    # 合并嵌套结构
    merged_root = merge_single_child_nodes(root)

    # 清理 false 属性
    clean_false_attributes(merged_root)

    # 清理空属性
    clean_empty_attributes(merged_root)

    # 清理 true 或非空属性
    clean_remove_true_or_non_empty_attributes(merged_root)

    new_tree = ET.ElementTree(merged_root)

    try:
        ET.indent(new_tree, space="    ")
    except Exception as e:
        print("Indent function is not available:", e)

    file_name = os.path.basename(input_path)
    output_file = os.path.join(output_path, file_name)
    new_tree.write(output_file, encoding="UTF-8", xml_declaration=True)
    print(f"处理完成，结果已保存到：{output_file}")


def get_compress_xml(ui_hierarchy_xml):
    root = ET.fromstring(ui_hierarchy_xml)

    # 合并嵌套结构
    merged_root = merge_single_child_nodes(root)

    # 清理 false 属性
    clean_false_attributes(merged_root)

    # 清理空属性
    clean_empty_attributes(merged_root)

    # 清理 true 或非空属性
    clean_remove_true_or_non_empty_attributes(merged_root)

    new_tree = ET.ElementTree(merged_root)

    try:
        ET.indent(new_tree, space="    ")
    except Exception as e:
        print("Indent function is not available:", e)

    xml_bytes = ET.tostring(merged_root, encoding='utf-8')
    xml_str = xml_bytes.decode('utf-8')
    return xml_str


def parse_bounds(bounds_str):
    """将 '[x1,y1][x2,y2]' 字符串转为整数坐标元组 (x1, y1, x2, y2)"""
    try:
        parts = bounds_str.strip("[]").split("][")
        (x1, y1) = map(int, parts[0].split(","))
        (x2, y2) = map(int, parts[1].split(","))
        return x1, y1, x2, y2
    except Exception:
        return 0, 0, 0, 0


def is_keyboard_active(ui_hierarchy_xml, screen_height, known_ime_packages=None):
    """
    判断给定的 UI XML 是否显示输入键盘（半通用逻辑）

    参数:
        xml_path (str): XML 文件路径（UI dump）
        known_ime_packages (list[str], optional): 输入法包名前缀列表
        screen_height (int): 屏幕高度

    返回:
        bool: True = 键盘激活，False = 未激活
    """
    if known_ime_packages is None:
        known_ime_packages = [
            "com.google.android.inputmethod",  # Gboard
            "com.sohu.inputmethod",  # 搜狗
            "com.baidu.input",  # 百度
            "com.huawei.ime",  # 华为
            "com.nolan.inputmethod",  # 小鹤双拼
            "com.iflytek.inputmethod",  # 讯飞
            "com.tencent.qqpinyin",  # QQ输入法
        ]

    try:
        root = ET.fromstring(ui_hierarchy_xml)
    except Exception as e:
        print("XML 解析失败:", e)
        return False

    for node in root.iter("node"):
        res_id = node.attrib.get("resource-id", "")
        class_name = node.attrib.get("class", "")
        visible = node.attrib.get("visible-to-user", "false") == "true"
        bounds_str = node.attrib.get("bounds", "")
        x1, y1, x2, y2 = parse_bounds(bounds_str)

        # 条件1：资源 ID 属于已知输入法包，且可见且靠近屏幕底部
        if any(res_id.startswith(pkg) for pkg in known_ime_packages):
            if visible and y2 >= screen_height * 0.85:
                return True

        # 条件2：系统输入法导航栏出现（Android 11+ 及以上）
        if res_id == "android:id/input_method_nav_buttons" and visible:
            return True

        # 条件3：某些 class 含 keyboard 或 ime 且位置接近底部
        if "keyboard" in class_name.lower() or "ime" in class_name.lower():
            if visible and y2 >= screen_height * 0.85:
                return True

    return False


if __name__ == "__main__":
    input_xml = "window_dump7.xml"
    output_dir = "compressXML"
    compressxml(input_xml, output_dir)
    # 默认以 'r'（只读）模式打开，编码为系统默认（通常 utf-8）
    with open("compressXML/window_dump7.xml", "r", encoding="utf-8") as f:
        content = f.read()  # 读取整个文件为字符串
    if is_keyboard_active(content,2400):
        print("✅ 输入键盘当前已激活")
    else:
        print("❌ 输入键盘未激活")