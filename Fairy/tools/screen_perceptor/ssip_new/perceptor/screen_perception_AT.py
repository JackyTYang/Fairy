from copy import deepcopy

from Fairy.tools.screen_perceptor.ssip_new.screen_AT import ScreenAccessibilityTree


class ScreenPerceptionAccessibilityTree(ScreenAccessibilityTree):
    def __init__(self, at_xml: str, target_app: None):
        super().__init__(at_xml, target_app)

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

    def get_nodes_need_marked(self, set_mark=False):
        index = 0
        nodes_need_marked = {
            "clickable": {
                'node_bounds_list':{},
                'node_center_list':{},
                'node_info_list': {}  # 存储完整节点信息用于生成compressed_txt
            },
            "scrollable": {
                'node_bounds_list': {},
                'node_center_list': {},
                'node_info_list': {}
            }
        }

        # ⭐ 新增：收集所有节点用于遮挡检测
        all_clickable_nodes = []

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

        def _point_in_bounds(point, bounds):
            """判断点是否在矩形范围内

            Args:
                point: [x, y]
                bounds: [[x1, y1], [x2, y2]]

            Returns:
                bool
            """
            if not point or not bounds:
                return False
            if len(bounds) != 2 or len(bounds[0]) != 2 or len(bounds[1]) != 2:
                return False
            x, y = point
            x1, y1 = bounds[0]
            x2, y2 = bounds[1]
            return x1 <= x <= x2 and y1 <= y <= y2

        def _calculate_area(bounds):
            """计算矩形面积

            Args:
                bounds: [[x1, y1], [x2, y2]]

            Returns:
                int: 面积
            """
            if not bounds or len(bounds) != 2:
                return 0
            (x1, y1), (x2, y2) = bounds
            return max(0, (x2 - x1) * (y2 - y1))

        def _calculate_intersection(bounds1, bounds2):
            """计算两个矩形的交集面积

            Args:
                bounds1: [[x1, y1], [x2, y2]]
                bounds2: [[x1, y1], [x2, y2]]

            Returns:
                int: 交集面积
            """
            if not bounds1 or not bounds2:
                return 0

            (x1_1, y1_1), (x2_1, y2_1) = bounds1
            (x1_2, y1_2), (x2_2, y2_2) = bounds2

            # 计算交集矩形
            x1 = max(x1_1, x1_2)
            y1 = max(y1_1, y1_2)
            x2 = min(x2_1, x2_2)
            y2 = min(y2_1, y2_2)

            # 如果没有交集
            if x1 >= x2 or y1 >= y2:
                return 0

            return (x2 - x1) * (y2 - y1)

        def _is_view_occluded(node, all_nodes, occlusion_threshold=0.7):
            """检测View是否被其他View遮挡（基于面积法）

            Args:
                node: 当前节点
                all_nodes: 所有可点击节点列表（按访问顺序，后面的可能在上层）
                occlusion_threshold: 遮挡面积阈值（默认70%）

            Returns:
                bool: True表示被遮挡超过阈值
            """
            node_bounds = node.get('bounds')
            node_center = node.get('center')

            if not node_bounds or not node_center:
                return False

            # 计算节点的矩形面积
            node_area = _calculate_area(node_bounds)
            if node_area == 0:
                return False

            # 获取当前节点在列表中的索引
            try:
                node_index = all_nodes.index(node)
            except ValueError:
                return False

            # ⭐ 快速检查：如果中心点没被覆盖，大概率不被遮挡（性能优化）
            center_covered = False
            for upper_node in all_nodes[node_index + 1:]:
                upper_bounds = upper_node.get('bounds')
                if upper_bounds and _point_in_bounds(node_center, upper_bounds):
                    center_covered = True
                    break

            # 中心点未被覆盖 → 直接判定为不遮挡
            if not center_covered:
                return False

            # ⭐ 精确检查：计算遮挡面积
            total_occluded_area = 0

            # 检查所有在后面访问的节点（可能在上层）
            for upper_node in all_nodes[node_index + 1:]:
                upper_bounds = upper_node.get('bounds')
                if not upper_bounds:
                    continue

                # 计算交集面积
                intersection_area = _calculate_intersection(node_bounds, upper_bounds)
                total_occluded_area += intersection_area

            # 计算遮挡比例
            occlusion_ratio = total_occluded_area / node_area

            # 只有当遮挡超过阈值时才认为被遮挡
            if occlusion_ratio >= occlusion_threshold:
                node_id = node.get('resource-id', 'Unknown')
                node_text = node.get('text', '')[:20] if node.get('text') else ''

                print(f"⚠️  High occlusion detected:")
                print(f"   Occluded: [{node_id}] '{node_text}' at {node_center}")
                print(f"   Occlusion ratio: {occlusion_ratio:.1%} (threshold: {occlusion_threshold:.0%})")
                print(f"   Node area: {node_area}, Occluded area: {total_occluded_area}")
                return True

            return False

        def _add_node(node, type):
            nonlocal index

            # ⭐ 检查是否被遮挡（仅对clickable节点检测，减少性能开销）
            if type == "clickable" and _is_view_occluded(node, all_clickable_nodes):
                print(f"   → Skipped Mark {index} (occluded)")
                # 不增加index，直接跳过这个被遮挡的节点
                return node

            if set_mark: node["mark"] = index
            nodes_need_marked[type]['node_bounds_list'][index] = node["bounds"]
            nodes_need_marked[type]['node_center_list'][index] = node["center"]

            # ⭐ 提取所有文本（包括子节点）
            all_texts = _extract_all_text(node)
            combined_text = ' | '.join(all_texts) if all_texts else ''

            # 存储完整节点信息（确保与SoM_mapping索引一致）
            nodes_need_marked[type]['node_info_list'][index] = {
                'class': node.get('class', 'Unknown'),
                'resource-id': node.get('resource-id'),
                'text': combined_text,  # ⭐ 使用合并后的文本
                'center': node.get('center'),
                'bounds': node.get('bounds'),
                'properties': node.get('properties', [])
            }

            index = index + 1
            return node

        # ⭐ 第一遍遍历：收集所有可点击节点
        def _collect_clickable_nodes(node):
            if "clickable" in node['properties']:
                all_clickable_nodes.append(node)
            return node

        for at_node in self.at_dict:
            self._common_filter(at_node, _collect_clickable_nodes)

        # ⭐ 第二遍遍历：标记节点（会应用遮挡检测）
        def _clickable_and_scrollable_filter(node):
            if "clickable" in node['properties']:
                node = _add_node(node, "clickable")
            elif "scrollable" in node['properties']:
                node = _add_node(node, "scrollable")
            return node

        self.at_dict = [self._common_filter(at_node, _clickable_and_scrollable_filter) for at_node in self.at_dict]
        return nodes_need_marked

    async def _summarize_clickable_nodes(self, at_node, summarize_text_func):
        # 检查节点是否包含 'clickable' 属性
        def _is_node_clickable(node):
            return ('properties' in node and "clickable" in node['properties']) or ('merged-properties' in node and any('clickable' in props for props in node['merged-properties']))

        # 用于递归移除所有不包含 'clickable' 属性，且其所有子孙节点都不包含 'clickable' 的节点。
        def _prune_non_clickable(node):
            if 'children' not in node or len(node['children']) == 0: # 终止条件：没有 children
                return node if _is_node_clickable(node) else None
            pruned_children = []
            for child in node['children']:
                if _is_node_clickable(child):
                    pruned_children.append(child) # 子节点可以点击则不处理
                else:
                    pruned_child = _prune_non_clickable(child) # 递归处理子节点
                    if pruned_child is not None:
                        pruned_children.append(pruned_child)
            node['children'] = pruned_children
            if pruned_children or _is_node_clickable(node): # 当前节点是否保留
                return node
            return None
        # 遍历所有clickable节点
        node_successor_list = []
        def _clickable_filter(node):
            if _is_node_clickable(node):
                node_successor_list.append(deepcopy(node["children"]) if 'children' in node else [])
                node = _prune_non_clickable(node)  # 移除其下所有不包含 'clickable' 属性的节点
            return node
        at_node = self._common_filter(at_node, _clickable_filter)
        # 总结节点
        summarized_text_map = await summarize_text_func(node_successor_list)
        # 二次遍历所有clickable节点，添加总结
        index = 0
        def _clickable_filter(node):
            nonlocal index
            if _is_node_clickable(node):
                if summarized_text_map[index] is not None:
                    node["text"] = summarized_text_map[index]
                index = index + 1
            return node
        at_node = self._common_filter(at_node, _clickable_filter)
        return at_node

    async def get_page_description(self, summarize_text_func=None):
        page_desc = []
        for at_node in self.at_dict:
            at_node = self._common_filter(at_node, self._coordinate_filter)
            at_node = self._common_filter(at_node, self._redundant_info_filter)
            at_node = self._struct_compress(at_node)
            if summarize_text_func is not None:
                at_node = await self._summarize_clickable_nodes(at_node, summarize_text_func)
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

    # [生成页面描述时] 非可点击/滚动的元素无需提供坐标信息
    @staticmethod
    def _coordinate_filter(node):
        # if not any(k in node['properties'] for k in ('clickable', 'long-clickable', 'scrollable')):
        if 'clickable' not in node['properties'] and 'long-clickable' not in node['properties']:
            del node['bounds']
            del node['center']
        return node

    # [生成页面描述时] 清理冗余信息
    @staticmethod
    def _redundant_info_filter(node):
        # 删除不必要的信息，例如包名
        del node['package']
        del node['layer']
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