from copy import deepcopy

import xmltodict
import re

class ScreenAccessibilityTree:
    def __init__(self, at_xml: str):
        at_dict_raw = xmltodict.parse(at_xml)['hierarchy']['node']
        self.at_dict = [self._node_info_collector(at_node) for at_node in at_dict_raw]

    def _node_info_collector(self, at_node):
        at_node_info = {}
        # 收集类名、包名、资源ID
        at_node_info['class'] = at_node.get('@class')
        at_node_info['package'] = at_node.get('@package')
        at_node_info['resource-id'] = at_node.get('@resource-id') if at_node.get('@resource-id') != '' else None

        # 收集关键属性(非False)
        at_node_info['properties'] = []
        for key, value in at_node.items():
            if value and value != 'false' and key in ['@checkable', '@checked', '@clickable', '@enabled', '@focusable', '@focused', '@scrollable', '@long-clickable', '@password', '@selected', '@visible-to-user']:
                at_node_info['properties'].append(key.replace('@', ''))

        # 收集坐标信息
        bounds = at_node.get('@bounds') # 形如[x1,y1][x2,y2]的字符串
        # 正则表达式匹配方括号内的数字
        pattern = r'\[(\d+),(\d+)\]'
        matches = re.findall(pattern, bounds)
        bounds = [[int(x), int(y)] for x, y in matches] # 形如[[x1,y1],[x2,y2]]的数组
        at_node_info['bounds'] = bounds
        at_node_info['center'] = [ # 计算中心点坐标
            bounds[0][0] + ((bounds[1][0] - bounds[0][0]) // 2), bounds[0][1] + ((bounds[1][1] - bounds[0][1]) // 2)
        ]

        # 收集文本信息
        at_node_info['text'] = at_node.get('@text', None)

        # 递归处理子节点
        at_node_info['children'] = []
        node = at_node.get('node', [])
        for sub_node in node if isinstance(node, list) else [node]:
            at_node_info['children'].append(self._node_info_collector(sub_node))

        return at_node_info

    def _common_filter(self, node, filter):
        node = deepcopy(node)
        node = filter(node)

        if node.get('children') is not None:
            temporary_children = []
            for sub_node in node['children']:
                temporary_children.append(self._common_filter(sub_node, filter))
            node['children'] = temporary_children
        return node

    def get_nodes_need_visual_desc(self):
        node_bounds_list = []
        def _need_visual_filter(node):
            # 如果是叶子节点且类名为 ImageView 或 View，则需要视觉描述
            if len(node['children']) == 0 and node['class'] in ['android.widget.ImageView', 'android.view.View']:
                node_bounds_list.append(node['bounds'])
            return node

        for at_node in self.at_dict:
            self._common_filter(at_node, _need_visual_filter)
        return node_bounds_list

    def set_visual_desc_to_nodes(self, desc_map):
        index = 0
        def _need_visual_filter(node):
            nonlocal index
            # 如果是叶子节点且类名为 ImageView 或 View，则需要视觉描述
            if len(node['children']) == 0 and node['class'] in ['android.widget.ImageView', 'android.view.View']:
                node['text'] = desc_map[index]
                index = index + 1
            return node

        self.at_dict = [self._common_filter(at_node, _need_visual_filter) for at_node in self.at_dict]

    def get_page_description(self):
        page_desc = []
        for at_node in self.at_dict:
            at_node = self._common_filter(at_node, self._coordinate_filter)
            at_node = self._common_filter(at_node, self._redundant_info_filter)
            at_node = self._struct_compress(at_node)
            print(at_node)
            page_desc.append("\n".join(self._format_ui_tree(at_node)))
        return page_desc

    # 结构压缩，必须在冗余信息过滤后才能执行（有强假设）
    def _struct_compress(self, node):
        def merge_info(parent, child):
            if 'center' in parent and 'center' in child: # 均有坐标信息，说明均可点击，不能合并这种节点
                return parent
            elif 'center' in parent: # 父亲有坐标信息，说明可点击，将坐标信息传递给孩子留存
                child['bounds'] = parent['bounds']
                child['center'] = parent['center']

            # 初始化 merged 字段
            for key in ['class', 'resource-id', 'properties']:
                if key in parent:
                    child.setdefault(f'merged-{key}', [])
                    if parent[key] not in child[f'merged-{key}']:
                        child[f'merged-{key}'].append(parent[key])
            return child

        # 如果没有 children 或不是列表，直接返回
        if not isinstance(node, dict):
            return node
        children = node.get('children')
        if not isinstance(children, list):
            return node

        # 压缩当前节点
        while len(children) == 1:
            child = children[0]
            child = merge_info(node, child)
            node = child
            children = node.get('children', [])

        # 对每个子节点递归压缩
        if 'children' in node:
            node['children'] = [self._struct_compress(child) for child in node['children']]

        return node

    def _format_ui_tree(self, node, indent=0):
        lines = []

        # 合并 class 信息
        base_class = node.get('class', 'Unknown')
        merged_classes = node.get('merged-class', [])
        full_class = "/".join(merged_classes + [base_class]) if merged_classes else base_class

        # 合并 resource-id 信息
        base_id = node.get('resource-id')
        merged_ids = node.get('merged-resource-id', [])
        full_id = "/".join(merged_ids + [base_id]) if base_id and merged_ids else base_id

        # 合并属性（properties 和 merged-properties）
        props = set(node.get('properties', []))
        merged_props = node.get('merged-properties', [])
        for mp in merged_props:
            if isinstance(mp, list):
                props.update(mp)
            else:
                props.add(mp)
        props_text = f"[{', '.join(sorted(props))}]" if props else ""

        # 中心坐标
        center = node.get('center')
        center_text = f"[Center: {center}]" if center else ""

        # 文本内容
        text = node.get('text')
        text_text = f"[{text}]" if text else ""

        # 构建当前节点的描述
        desc_parts = [full_class]
        if full_id:
            desc_parts.append(f"({full_id})")
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
        for child in node.get('children', []):
            lines.extend(self._format_ui_tree(child, indent + 1))

        return lines

    # [生成页面描述时] 非可点击元素无需提供坐标信息
    @staticmethod
    def _coordinate_filter(node):
        if 'clickable' not in node['properties'] and 'long-clickable' not in node['properties']:
            del node['bounds']
            del node['center']
        return node

    # [生成页面描述时] 清理冗余信息
    @staticmethod
    def _redundant_info_filter(node):
        # 删除不必要的信息，例如包名
        del node['package']
        # 简化不必要的类名
        node['class'] = node['class'].split('.')[-1].replace("ImageView", "Img").replace("TextView", "Txt")
        # 简化不必要的资源ID
        if node['resource-id'] is None:
            del node['resource-id']
        else:
            node['resource-id'] = node['resource-id'].split('/')[-1]
        # 删除不必要的属性
        for key in list(node['properties']):
            if key in ['enabled', 'visible-to-user']:
                node['properties'].remove(key)
        # 删除空的属性
        if not node['properties']:
            del node['properties']
        # 删除空的文本信息
        if not node.get('text'):
            del node['text']
        # 删除空的子节点
        if len(node['children']) == 0 :
            del node['children']
        return node


if __name__ == '__main__':
    with open("E.xml", "r", encoding="utf-8") as f:
        content = f.read()  # 读取整个文件为字符串
    at = ScreenAccessibilityTree(content)
    print(at.get_page_description())