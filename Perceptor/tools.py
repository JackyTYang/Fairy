import subprocess
import os
from datetime import datetime

from sympy import capture


class UIAutomatorCapture:
    def __init__(self, adb_path="/Users/jackyyang/android_sdk/platform-tools/adb", output_dir="./captures", use_singleton=False, device_id=None):
        """
        Args:
            adb_path: ADB路径
            output_dir: 输出目录
            use_singleton: 是否使用单例设备连接（uiautomator2）
            device_id: 设备ID
        """
        self.adb_path = adb_path
        self.output_dir = output_dir
        self.use_singleton = use_singleton
        self.device_id = device_id
        os.makedirs(output_dir, exist_ok=True)

        if use_singleton:
            # 使用单例 uiautomator2 设备
            from shared import DeviceManager
            self.dev = DeviceManager.get_device(device_id)
        else:
            self.dev = None

    def capture(self):
        """捕获当前屏幕的XML和截图"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 创建单独的文件夹
        capture_folder = os.path.join(self.output_dir, timestamp)
        os.makedirs(capture_folder, exist_ok=True)

        if self.use_singleton:
            # 使用 uiautomator2 单例设备
            return self._capture_with_u2(timestamp, capture_folder)
        else:
            # 使用 adb 命令
            return self._capture_with_adb(timestamp, capture_folder)

    def _capture_with_u2(self, timestamp, capture_folder):
        """使用 uiautomator2 捕获"""
        # 截图文件路径
        screenshot_filename = f"screenshot_{timestamp}.png"
        screenshot_local_path = os.path.abspath(os.path.join(capture_folder, screenshot_filename))

        # XML文件路径
        xml_filename = f"ui_dump_{timestamp}.xml"
        xml_local_path = os.path.abspath(os.path.join(capture_folder, xml_filename))

        # 1. 捕获截图
        self.dev.screenshot(screenshot_local_path)

        # 2. 捕获UI XML
        ui_xml = self.dev.dump_hierarchy()
        with open(xml_local_path, 'w', encoding='utf-8') as f:
            f.write(ui_xml)

        # 3. 从截图文件读取尺寸
        from PIL import Image
        img = Image.open(screenshot_local_path)
        width, height = img.size

        return {
            "screenshot_path": screenshot_local_path,
            "xml_path": xml_local_path,
            "ui_xml": ui_xml,
            "screen_size": [width, height],
            "timestamp": timestamp,
            "capture_folder": capture_folder
        }

    def _capture_with_adb(self, timestamp, capture_folder):
        """使用 adb 命令捕获"""
        # XML文件路径
        xml_filename = f"ui_dump_{timestamp}.xml"
        xml_local_path = os.path.abspath(os.path.join(capture_folder, xml_filename))
        xml_device_path = f"/sdcard/{xml_filename}"

        # 截图文件路径
        screenshot_filename = f"screenshot_{timestamp}.png"
        screenshot_local_path = os.path.abspath(os.path.join(capture_folder, screenshot_filename))
        screenshot_device_path = f"/sdcard/{screenshot_filename}"

        # 1. 捕获UI XML
        subprocess.run([self.adb_path, "shell", "uiautomator", "dump", xml_device_path],
                      check=True)
        subprocess.run([self.adb_path, "pull", xml_device_path, xml_local_path],
                      check=True)
        subprocess.run([self.adb_path, "shell", "rm", xml_device_path])

        # 2. 捕获截图
        subprocess.run([self.adb_path, "shell", "screencap", "-p", screenshot_device_path],
                      check=True)
        subprocess.run([self.adb_path, "pull", screenshot_device_path, screenshot_local_path],
                      check=True)
        subprocess.run([self.adb_path, "shell", "rm", screenshot_device_path])

        # 3. 从截图文件读取尺寸
        from PIL import Image
        img = Image.open(screenshot_local_path)
        width, height = img.size

        # 4. 读取XML内容
        with open(xml_local_path, 'r', encoding='utf-8') as f:
            ui_xml = f.read()

        return {
            "screenshot_path": screenshot_local_path,
            "xml_path": xml_local_path,
            "ui_xml": ui_xml,
            "screen_size": [width, height],
            "timestamp": timestamp,
            "capture_folder": capture_folder  # 返回文件夹路径
        }


class XMLCompressor:
    """使用 MobileAgentX 的快速压缩方法压缩 XML（基于 ElementTree 就地修改）"""

    # 定义布尔属性列表
    BOOL_ATTRS = {
        "checkable", "checked", "clickable", "enabled", "focusable",
        "focused", "scrollable", "long-clickable", "password", "selected"
    }

    MEANINGFUL_BOOL_ATTRS = {
        "checkable", "checked", "clickable", "focusable",
        "focused", "scrollable", "long-clickable", "password", "selected"
    }

    # 配置：哪些布尔属性即使为 "false" 也保留
    KEEP_FALSE_BOOLEAN_ATTRS = {"enabled"}

    # 配置：哪些非布尔属性为空时保留
    KEEP_EMPTY_STRING_ATTRS = {"package", "content-desc"}

    # 配置：哪些属性即使为 "true" 或不为空也不保留
    REMOVE_IF_TRUE_OR_NON_EMPTY = {"package"}

    def __init__(self, output_dir="./captures"):
        self.output_dir = output_dir

    async def compress_xml(self, ui_xml, timestamp, target_app=None):
        """
        压缩 XML 并保存（使用 MobileAgentX 快速算法），同时生成 Fairy 的文本描述格式

        Args:
            ui_xml: 原始UI XML字符串
            timestamp: 时间戳
            target_app: 目标应用包名（可选，暂不使用）

        Returns:
            (压缩后的 XML 文件路径, 文本描述文件路径)
        """
        import xml.etree.ElementTree as ET
        import time

        print("正在压缩XML（使用 MobileAgentX 快速算法）...")
        start_time = time.time()

        # 解析 XML
        root = ET.fromstring(ui_xml)

        # 压缩
        compressed_root = self._compress_xml_node(root)

        # 1. 写入压缩后的 XML
        new_tree = ET.ElementTree(compressed_root)
        try:
            ET.indent(new_tree, space="  ")
        except Exception:
            pass  # Python 3.9 以下版本不支持 indent

        compressed_xml_path = os.path.join(self.output_dir, f"compressed_{timestamp}.xml")
        new_tree.write(compressed_xml_path, encoding="UTF-8", xml_declaration=True)

        # 2. 转换为 Fairy 的文本描述格式
        text_desc = self._format_ui_tree_to_text(compressed_root)
        text_path = os.path.join(self.output_dir, f"compressed_{timestamp}.txt")
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text_desc)

        elapsed = time.time() - start_time
        print(f"压缩完成:")
        print(f"  XML: {compressed_xml_path}")
        print(f"  文本描述: {text_path}")
        print(f"耗时: {elapsed:.3f} 秒")
        return compressed_xml_path, text_path

    def _format_ui_tree_to_text(self, node, indent=0):
        """将 ElementTree 节点格式化为 Fairy 的文本描述格式"""
        lines = []

        # 合并 class 信息
        base_class = node.get('class', 'Unknown')
        full_class = base_class.split('.')[-1] if base_class else 'Unknown'

        # 资源 ID
        resource_id = node.get('resource-id', '')
        id_text = f"({resource_id})" if resource_id else ""

        # 文本内容
        text = node.get('text', '').strip()
        text_text = f"[{text}]" if text else ""

        # 中心坐标
        center = node.get('center', '')
        center_text = f"[Center: {center}]" if center else ""

        # 属性
        props = self._parse_properties(node)
        props_text = f"[{', '.join(sorted(props))}]" if props else ""

        # 构建当前节点的描述
        desc_parts = [full_class]
        if id_text:
            desc_parts.append(id_text)
        if text_text:
            desc_parts.append(text_text)
        if center_text:
            desc_parts.append(center_text)
        if props_text:
            desc_parts.append(props_text)

        # 输出行
        line = "  " * indent + "- " + " ".join(desc_parts)
        lines.append(line)

        # 递归子节点
        for child in node:
            lines.append(self._format_ui_tree_to_text(child, indent + 1))

        return "\n".join(lines)

    def _parse_properties(self, node):
        """从节点的布尔属性中提取 properties 列表"""
        props = []
        for attr in ['clickable', 'scrollable', 'checkable', 'checked', 'focusable', 'focused', 'long-clickable', 'password', 'selected']:
            if node.get(attr, 'false') == 'true':
                props.append(attr)
        return props

    def _compress_xml_node(self, root):
        """
        对传入的 XML 根节点执行压缩操作，包括嵌套合并、无意义节点删除等，返回压缩后的根节点。
        （基于 MobileAgentX 的实现）
        """
        merged_root = self._merge_single_child_nodes(root)

        for _ in range(3):
            merged_root = self._delete_meaningless_node(merged_root)
            merged_root = self._merge_single_child_nodes(merged_root)

        self._clean_false_attributes(merged_root)
        self._clean_empty_attributes(merged_root)
        self._clean_remove_true_or_non_empty_attributes(merged_root)
        self._add_bounds_center_attribute(merged_root)

        return merged_root

    def _merge_attributes(self, parent_attrib, child_attrib):
        """合并父节点与子节点的属性（不删除 false，统一在后处理）"""
        merged = child_attrib.copy()
        for key, p_val in parent_attrib.items():
            if key in self.BOOL_ATTRS:
                c_val = child_attrib.get(key, "false")
                merged[key] = "true" if (p_val.lower() == "true" or c_val.lower() == "true") else "false"
            else:
                c_val = child_attrib.get(key, "")
                if not c_val.strip() and p_val.strip():
                    merged[key] = p_val
        return merged

    def _merge_single_child_nodes(self, node):
        """合并仅包含单一子节点的结构，提升子节点"""
        children = list(node)
        for child in children:
            merged_child = self._merge_single_child_nodes(child)
            node.remove(child)
            node.append(merged_child)

        while len(node) == 1:
            child = node[0]
            child.attrib = self._merge_attributes(node.attrib, child.attrib)
            if node.text and node.text.strip():
                if child.text and child.text.strip():
                    child.text = node.text.strip() + " " + child.text.strip()
                else:
                    child.text = node.text.strip()
            node = child
        return node

    def _delete_meaningless_node(self, node):
        """删除无意义的节点（后根遍历）"""
        children_to_keep = []
        for child in list(node):
            pruned_child = self._delete_meaningless_node(child)
            if pruned_child is not None:
                children_to_keep.append(pruned_child)
        node[:] = children_to_keep  # 更新子节点列表

        # 如果是叶子节点且满足条件，返回 None 表示删除
        if len(node) == 0:
            all_false = all(node.get(attr) == "false" for attr in self.MEANINGFUL_BOOL_ATTRS)
            text_empty = not node.get("text", "").strip()
            not_image_view = node.get("class") != "android.widget.ImageView"

            if all_false and text_empty and not_image_view:
                return None  # 删除该节点

            # 判断是否是 ImageView，并且 clickable 和 long-clickable 都为 false
            if node.get("class") == "android.widget.ImageView":
                clickable = node.get("clickable", "false") == "true"
                long_clickable = node.get("long-clickable", "false") == "true"
                if not clickable and not long_clickable:
                    return None  # 删除该节点

        return node  # 保留该节点

    def _clean_false_attributes(self, node):
        """遍历所有节点，删除值为 false 且不在保留列表中的布尔属性"""
        keys_to_delete = [
            k for k, v in node.attrib.items()
            if k in self.BOOL_ATTRS and v.lower() == "false" and k not in self.KEEP_FALSE_BOOLEAN_ATTRS
        ]
        for k in keys_to_delete:
            del node.attrib[k]
        for child in node:
            self._clean_false_attributes(child)

    def _clean_empty_attributes(self, node):
        """遍历所有节点，删除值为空的属性（只删除空属性且不在保留列表中）"""
        keys_to_delete = [
            k for k, v in node.attrib.items()
            if not v.strip() and k not in self.KEEP_EMPTY_STRING_ATTRS
        ]
        for k in keys_to_delete:
            del node.attrib[k]
        for child in node:
            self._clean_empty_attributes(child)

    def _clean_remove_true_or_non_empty_attributes(self, node):
        """遍历所有节点，删除即使为 true 或非空的属性，如果在配置项中"""
        keys_to_delete = [
            k for k, v in node.attrib.items()
            if k in self.REMOVE_IF_TRUE_OR_NON_EMPTY and (v.lower() == "true" or v.strip())
        ]
        for k in keys_to_delete:
            del node.attrib[k]
        for child in node:
            self._clean_remove_true_or_non_empty_attributes(child)

    def _add_bounds_center_attribute(self, node):
        """给每个包含 bounds 属性的节点添加一个 center 属性，表示其中心点坐标"""
        bounds = node.attrib.get("bounds", "")
        if bounds:
            try:
                # 假设 bounds 为 "[left, top][right, bottom]"
                bounds_values = bounds.strip("[]").split("][")

                if len(bounds_values) == 2:
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
            self._add_bounds_center_attribute(child)


if __name__ == "__main__":
    import asyncio

    async def compress():
        # 1. 捕获屏幕
        print("=" * 50)
        print("开始捕获屏幕...")
        capturer = UIAutomatorCapture(
            adb_path="/Users/jackyyang/android_sdk/platform-tools/adb",
            output_dir="./captures"
        )
        capture_data = capturer.capture()

        print(f"\n已捕获到文件夹: {capture_data['capture_folder']}")
        print(f"  截图: {capture_data['screenshot_path']}")
        print(f"  XML: {capture_data['xml_path']}")
        print(f"  屏幕尺寸: {capture_data['screen_size']}")

        # 2. 压缩XML（MobileAgentX 算法 + 转换为 Fairy 文本格式）
        print("\n" + "=" * 50)
        compressor = XMLCompressor(output_dir=capture_data['capture_folder'])
        compressed_xml, compressed_txt = await compressor.compress_xml(
            ui_xml=capture_data['ui_xml'],
            timestamp=capture_data['timestamp'],
            target_app=None
        )

        print("\n" + "=" * 50)
        print("所有任务完成!")
        print(f"文件夹: {capture_data['capture_folder']}")
        print(f"  - 原始XML: {os.path.basename(capture_data['xml_path'])}")
        print(f"  - 压缩XML: {os.path.basename(compressed_xml)}")
        print(f"  - 文本描述: {os.path.basename(compressed_txt)}")
        print(f"  - 截图: {os.path.basename(capture_data['screenshot_path'])}")
        print("=" * 50)

    asyncio.run(compress())