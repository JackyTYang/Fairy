#!/usr/bin/env python3
"""
测试遮挡检测功能

使用之前的问题案例（20251223_145104 step_1）验证遮挡检测是否工作
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from Fairy.tools.screen_perceptor.ssip_new.perceptor.screen_perception_AT import ScreenPerceptionAccessibilityTree

def test_occlusion_detection():
    """测试遮挡检测功能"""

    # 使用问题案例的XML文件
    xml_path = project_root / "integration/output/exploration/20251223_145104/step_1/stable/ui_dump_1766472750.xml"

    if not xml_path.exists():
        print(f"❌ XML文件不存在: {xml_path}")
        return

    print(f"✓ 加载XML文件: {xml_path}")

    with open(xml_path, 'r', encoding='utf-8') as f:
        xml_content = f.read()

    # 创建ScreenPerceptionAccessibilityTree实例
    screen_at = ScreenPerceptionAccessibilityTree(xml_content, target_app=None)

    print("\n" + "="*60)
    print("开始标注可点击节点（启用遮挡检测）")
    print("="*60 + "\n")

    # 获取标注节点（会触发遮挡检测）
    nodes_marked = screen_at.get_nodes_need_marked(set_mark=True)

    print("\n" + "="*60)
    print("标注结果统计")
    print("="*60)

    clickable_count = len(nodes_marked['clickable']['node_bounds_list'])
    scrollable_count = len(nodes_marked['scrollable']['node_bounds_list'])

    print(f"\n可点击节点数: {clickable_count}")
    print(f"可滚动节点数: {scrollable_count}")

    print("\n前10个可点击节点:")
    for mark_id in sorted(list(nodes_marked['clickable']['node_info_list'].keys())[:10]):
        info = nodes_marked['clickable']['node_info_list'][mark_id]
        text = info['text'][:30] if info['text'] else '(no text)'
        resource_id = info['resource-id'] if info['resource-id'] else '(no id)'
        center = info['center']
        print(f"  Mark {mark_id}: [{resource_id}] '{text}' at {center}")

    print("\n✓ 测试完成！")
    print("\n预期结果:")
    print("  - 应该看到遮挡检测的警告信息")
    print("  - 被优惠券浮层遮挡的'鸡肉汉堡/卷'分类应该被跳过")
    print("  - Mark编号应该自动调整，避开被遮挡的元素")

if __name__ == "__main__":
    test_occlusion_detection()
