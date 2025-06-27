from copy import deepcopy

import xmltodict
import re

from loguru import logger


class ScreenAccessibilityTree:
    def __init__(self, at_xml: str, target_app: None):
        self.at_xml_raw = at_xml
        self.at_dict_raw = xmltodict.parse(self.at_xml_raw)['hierarchy']['node']
        self.at_dict = []
        for at_node in self.at_dict_raw:
            if target_app is not None:
                if '@package' in at_node and at_node['@package'] == target_app :
                    self.at_dict.append(self._node_info_collector(at_node))
                else:
                    logger.bind(log_tag="fairy_sys").info(
                        f"[Screen Perception] The nodes of package {at_node['@package']} have been ignored because the app package was specified!")
            else:
                self.at_dict.append(self._node_info_collector(at_node))
        if len(self.at_dict) == 0:
            logger.bind(log_tag="fairy_sys").warning(
                f"[Screen Perception] The node specifying the app package {target_app} was not found in the screen.")

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
        at_node_info['text'] = at_node.get('@text', None).replace("\n","")

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