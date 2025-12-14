import hashlib
import os
import uuid
import xml.etree.ElementTree as ET

from config.config import initialize_config

# 定义布尔属性列表
BOOL_ATTRS = {
    "checkable", "checked", "clickable", "enabled", "focusable",
    "focused", "scrollable", "long-clickable", "password", "selected"
}

MEANINGFUL_BOOL_ATTRS = {
    "checkable", "checked", "clickable", "focusable",
    "focused", "scrollable", "long-clickable", "password", "selected"
}

# ✅ 全局配置：用于生成节点路径哈希 ID 的属性字段
HASH_PATH_ATTRS = ["class", "resource-id"]

# 配置：哪些布尔属性即使为 "false" 也保留
KEEP_FALSE_BOOLEAN_ATTRS = {"enabled"}  # 例如保留 "enabled", "focusable" 为 false 时的属性

# 配置：哪些非布尔属性为空时保留
KEEP_EMPTY_STRING_ATTRS = {"package", "content-desc"}  # 例如保留空的 "resource-ID", "text" 等

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


def add_bounds_center_attribute(node):
    """
    给每个包含 bounds 属性的节点添加一个 center 属性，表示其中心点坐标。
    假设 bounds 格式为 "[left, top][right, bottom]"。
    """
    bounds = node.attrib.get("bounds", "")
    if bounds:
        try:
            # 假设bounds为 "[left, top][right, bottom]"
            # 去掉方括号并按 '][' 分割
            bounds_values = bounds.strip("[]").split("][")

            if len(bounds_values) == 2:
                # 解析左上和右下坐标
                left_top = bounds_values[0].split(",")
                right_bottom = bounds_values[1].split(",")

                if len(left_top) == 2 and len(right_bottom) == 2:
                    left, top = map(int, left_top)
                    right, bottom = map(int, right_bottom)

                    # 计算中心点坐标
                    center_x = (left + right) / 2
                    center_y = (top + bottom) / 2
                    node.attrib["center"] = f"[{center_x},{center_y}]"
        except ValueError:
            pass  # 如果解析失败，忽略该节点
    for child in node:
        add_bounds_center_attribute(child)

def delete_meaningless_node(node):
    # 后根遍历子节点
    children_to_keep = []
    for child in list(node):
        pruned_child = delete_meaningless_node(child)
        if pruned_child is not None:
            children_to_keep.append(pruned_child)
    node[:] = children_to_keep  # 更新子节点列表

    # 如果是叶子节点且满足条件，返回 None 表示删除
    if len(node) == 0:
        all_false = all(node.get(attr) == "false" for attr in MEANINGFUL_BOOL_ATTRS)
        text_empty = not node.get("text", "").strip()
        not_image_view = node.get("class") != "android.widget.ImageView"

        if all_false and text_empty and not_image_view:
            return None  # 删除该节点

        # 判断是否是 ImageView，并且 clickable 和 long-clickable 都为 false
        if node.get("class") == "android.widget.ImageView":
            clickable = node.get("clickable", "false") == "true"
            long_clickable = node.get("long-clickable", "false") == "true"
            if not clickable and not long_clickable:
                return None  # 如果是 ImageView 且 clickable 和 long-clickable 都为 false，删除该节点

    return node  # 保留该节点


def add_only_id_to_nodes(root: ET.Element) -> ET.Element:
    """
    遍历整个 XML 树，为每个节点添加全局唯一的 only-id 属性。
    生成规则使用 UUID，确保无重复。

    参数：
        root: XML 的根节点（Element）

    返回：
        添加了 only-id 的根节点
    """
    for node in root.iter():
        unique_id = str(uuid.uuid4())
        node.set("only-id", unique_id)

    return root

def remove_only_id_to_nodes(root: ET.Element) -> ET.Element:
    """
    遍历整个 XML 树，为每个节点添加全局唯一的 only-id 属性。
    生成规则使用 UUID，确保无重复。

    参数：
        root: XML 的根节点（Element）

    返回：
        添加了 only-id 的根节点
    """
    for node in root.iter():
        node.attrib.pop("only-id", None)  # 删除 "function" 属性，如果不存在则不做任何事

    return root

def add_hashed_id_to_nodes(root: ET.Element) -> ET.Element:
    """
    给每个 XML 节点添加唯一 ID 属性，基于从根到当前节点的路径哈希。

    参数:
    - root: ElementTree 根节点

    使用全局变量 HASH_PATH_ATTRS 控制参与路径构造的属性字段。
    """
    def build_path(node, path_stack):
        # 当前节点的路径标识（基于 HASH_PATH_ATTRS）
        parts = []
        for attr in HASH_PATH_ATTRS:
            val = node.get(attr, "")
            parts.append(f"{attr}={val}")
        key = "|".join(parts)
        path_stack.append(key)

        # 构造 hash ID
        full_path = "/".join(path_stack)
        hashed = hashlib.md5(full_path.encode("utf-8")).hexdigest()
        node.set("ID", hashed)

        # 递归子节点
        for child in node.findall("node"):
            build_path(child, path_stack[:])  # 复制 path_stack，防止污染

    build_path(root, [])
    return root

def add_ids_and_save(xml_path):
    """
    给 cfg.target_xml 中的所有节点添加哈希 ID，并覆盖保存该 XML 文件。
    """
    # 1. 加载 XML
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 2. 添加 hashed ID
    add_hashed_id_to_nodes(root)

    # 3. 保存回原文件（覆盖）
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)

    print(f"✅ 已为 {xml_path} 所有节点添加 ID，并覆盖保存。")


def add_only_id_and_save(xml_path):
    """
    给 cfg.target_xml 中的所有节点添加only-id，并覆盖保存该 XML 文件。用来学习assm后patch，一对一
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    add_only_id_to_nodes(root)
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)
    print(f"✅ 已为 {xml_path} 所有节点添加 only-id，并覆盖保存。")

def remove_only_id_and_save(xml_path):
    """
    给 cfg.target_xml 中的所有节点添加only-id，并覆盖保存该 XML 文件。用来学习assm后patch，一对一
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    remove_only_id_to_nodes(root)
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)
    print(f"✅ 已为 {xml_path} 所有节点移除 only-id，并覆盖保存。")

def compressxml(cfg):
    tree = ET.parse(cfg.target_xml)
    root = tree.getroot()

    # 压缩
    compressed_root = compress_xml_node(root)

    # 写入压缩结果
    new_tree = ET.ElementTree(compressed_root)
    try:
        ET.indent(new_tree, space="    ")
    except Exception as e:
        print("Indent function is not available:", e)

    file_name = os.path.basename(cfg.target_xml)
    output_file = os.path.join(cfg.assm_compressedXML, file_name)
    cfg.assm_compressedXML = output_file
    new_tree.write(output_file, encoding="UTF-8", xml_declaration=True)
    print(f"处理完成，结果已保存到：{output_file}")


def compress_xml_node(root: ET.Element) -> ET.Element:
    """
    对传入的 XML 根节点执行压缩操作，包括嵌套合并、无意义节点删除等，返回压缩后的根节点。
    """
    merged_root = merge_single_child_nodes(root)

    for _ in range(3):
        merged_root = delete_meaningless_node(merged_root)
        merged_root = merge_single_child_nodes(merged_root)

    clean_false_attributes(merged_root)
    clean_empty_attributes(merged_root)
    clean_remove_true_or_non_empty_attributes(merged_root)
    add_bounds_center_attribute(merged_root)

    return merged_root


if __name__ == "__main__":
    input_xml = "/Users/jackyyang/Desktop/端侧大模型/code/MobileAgentX/static/ASSM/xml/实习.xml"
    output_dir = "/Users/jackyyang/Desktop/端侧大模型/code/MobileAgentX/pkg/transform/tools"
    config = initialize_config()
    config.target_xml = input_xml
    config.assm_compressedXML = output_dir

    compressxml(config)