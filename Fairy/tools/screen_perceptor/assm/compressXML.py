import os
import xml.etree.ElementTree as ET
import re

# 布尔属性
BOOL_ATTRS = {
    "checkable", "checked", "clickable", "enabled", "focusable",
    "focused", "scrollable", "long-clickable", "password", "selected"
}

KEEP_FALSE_BOOLEAN_ATTRS = {""}
KEEP_EMPTY_STRING_ATTRS = {"package"}
REMOVE_IF_TRUE_OR_NON_EMPTY = {"package", "class", "index"}


def merge_attributes(parent_attrib, child_attrib):
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
    keys_to_delete = [
        k for k, v in node.attrib.items()
        if k in BOOL_ATTRS and v.lower() == "false" and k not in KEEP_FALSE_BOOLEAN_ATTRS
    ]
    for k in keys_to_delete:
        del node.attrib[k]
    for child in node:
        clean_false_attributes(child)


def clean_empty_attributes(node):
    keys_to_delete = [
        k for k, v in node.attrib.items()
        if not v.strip() and k not in KEEP_EMPTY_STRING_ATTRS
    ]
    for k in keys_to_delete:
        del node.attrib[k]
    for child in node:
        clean_empty_attributes(child)


def clean_remove_true_or_non_empty_attributes(node):
    keys_to_delete = [
        k for k, v in node.attrib.items()
        if k in REMOVE_IF_TRUE_OR_NON_EMPTY and (v.lower() == "true" or v.strip())
    ]
    for k in keys_to_delete:
        del node.attrib[k]
    for child in node:
        clean_remove_true_or_non_empty_attributes(child)


def add_bounds_center_attribute(node):
    bounds = node.attrib.get("bounds", "")
    if bounds:
        try:
            bounds_values = bounds.strip("[]").split("][")
            if len(bounds_values) == 2:
                left_top = bounds_values[0].split(",")
                right_bottom = bounds_values[1].split(",")
                if len(left_top) == 2 and len(right_bottom) == 2:
                    left, top = map(int, left_top)
                    right, bottom = map(int, right_bottom)
                    center_x = (left + right) / 2
                    center_y = (top + bottom) / 2
                    node.attrib["center"] = f"[{center_x},{center_y}]"
        except ValueError:
            pass
    for child in node:
        add_bounds_center_attribute(child)


def simplify_true_booleans(node):
    keys_to_convert = []
    keys_to_delete = []

    for k, v in node.attrib.items():
        if k in BOOL_ATTRS:
            if v.lower() == "true":
                keys_to_convert.append(k)
            elif v.lower() == "false":
                keys_to_delete.append(k)

    for k in keys_to_delete:
        del node.attrib[k]
    for k in keys_to_convert:
        node.attrib[k] = "__VALLESS__"  # 防止 ElementTree 报错

    for child in node:
        simplify_true_booleans(child)


def tostring_with_valueless_true(node):
    xml_str = ET.tostring(node, encoding='unicode')
    # 替换 key="__VALLESS__" 为 key
    xml_str = re.sub(r'\s+(\w+)="__VALLESS__"', r' \1', xml_str)
    return xml_str


# ✅ 新增：为了解析 val-less 形式的 XML，补全为 key="true"
def fix_valueless_attributes_for_parsing(xml_str):
    # 将 <node clickable> 替换为 <node clickable="true">
    def replacer(match):
        tag, attrs = match.groups()
        fixed_attrs = re.sub(r'\s+(\w+)(?=\s|>|/)', r' \1="true"', attrs)
        return f"<{tag}{fixed_attrs}>"
    return re.sub(r'<(\w+)((?:\s+\w+)+)\s*/?>', replacer, xml_str)


def compressxml(input_path, output_path):
    tree = ET.parse(input_path)
    root = tree.getroot()

    merged_root = merge_single_child_nodes(root)
    clean_false_attributes(merged_root)
    clean_empty_attributes(merged_root)
    clean_remove_true_or_non_empty_attributes(merged_root)
    simplify_true_booleans(merged_root)
    add_bounds_center_attribute(merged_root)

    compressed_str = tostring_with_valueless_true(merged_root)
    file_name = os.path.basename(input_path)
    output_file = os.path.join(output_path, file_name)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(compressed_str)
    print(f"✅ 处理完成，结果已保存到：{output_file}")


def get_compress_xml(ui_hierarchy_xml):
    root = ET.fromstring(ui_hierarchy_xml)
    merged_root = merge_single_child_nodes(root)
    clean_false_attributes(merged_root)
    clean_empty_attributes(merged_root)
    clean_remove_true_or_non_empty_attributes(merged_root)
    simplify_true_booleans(merged_root)
    add_bounds_center_attribute(merged_root)
    return tostring_with_valueless_true(merged_root)


def parse_bounds(bounds_str):
    try:
        parts = bounds_str.strip("[]").split("][")
        (x1, y1) = map(int, parts[0].split(","))
        (x2, y2) = map(int, parts[1].split(","))
        return x1, y1, x2, y2
    except Exception:
        return 0, 0, 0, 0


def is_keyboard_active(ui_hierarchy_xml, screen_height, known_ime_packages=None):
    if known_ime_packages is None:
        known_ime_packages = [
            "com.google.android.inputmethod", "com.sohu.inputmethod",
            "com.baidu.input", "com.huawei.ime", "com.nolan.inputmethod",
            "com.iflytek.inputmethod", "com.tencent.qqpinyin"
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

        if any(res_id.startswith(pkg) for pkg in known_ime_packages):
            if visible and y2 >= screen_height * 0.85:
                return True
        if res_id == "android:id/input_method_nav_buttons" and visible:
            return True
        if "keyboard" in class_name.lower() or "ime" in class_name.lower():
            if visible and y2 >= screen_height * 0.85:
                return True

    return False


if __name__ == "__main__":
    input_xml = "window_dump7.xml"
    output_dir = ""
    # 默认以 'r'（只读）模式打开，编码为系统默认（通常 utf-8）
    with open("window_dump7.xml", "r", encoding="utf-8") as f:
        content = f.read()  # 读取整个文件为字符串
    if is_keyboard_active(content,2400):
        print("✅ 输入键盘当前已激活")
    else:
        print("❌ 输入键盘未激活")

    compressxml(input_xml, output_dir)