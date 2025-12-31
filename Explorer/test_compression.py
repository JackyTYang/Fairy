#!/usr/bin/env python3
"""
测试feature_tree压缩功能
"""

import json
from pathlib import Path
from entities import FeatureTree, FeatureNode, PageState, PathStep, PerceptionOutput

def load_and_compress_tree(tree_path: Path):
    """加载完整的feature_tree并生成压缩版"""
    print(f"加载: {tree_path}")

    with open(tree_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 重建FeatureTree对象
    tree = FeatureTree(root_feature_id=data['root_feature_id'])

    # 重建features
    for fid, f_data in data['features'].items():
        feature = FeatureNode(
            feature_id=fid,
            feature_name=f_data['feature_name'],
            feature_description=f_data['feature_description'],
            parent_feature_id=f_data.get('parent_feature_id'),
            states=f_data.get('states', []),
            sub_features=f_data.get('sub_features', []),
            entry_state_id=f_data.get('entry_state_id'),
            status=f_data.get('status', 'exploring'),
            completed_at=f_data.get('completed_at')
        )
        tree.features[fid] = feature

    # 重建states和steps
    for sid, s_data in data['states'].items():
        # 重建perception_output
        perception_output = PerceptionOutput(
            screenshot_path=s_data['perception_output']['screenshot_path'],
            marked_screenshot_path=s_data['perception_output']['marked_screenshot_path'],
            xml_path=s_data['perception_output']['xml_path'],
            compressed_xml_path=s_data['perception_output']['compressed_xml_path'],
            compressed_txt_path=s_data['perception_output']['compressed_txt_path'],
            som_mapping_path=s_data['perception_output']['som_mapping_path'],
            timestamp=s_data['perception_output']['timestamp'],
            screen_size=tuple(s_data['perception_output']['screen_size']),
            immediate_screenshot_path=s_data['perception_output'].get('immediate_screenshot_path'),
            immediate_marked_screenshot_path=s_data['perception_output'].get('immediate_marked_screenshot_path'),
            immediate_xml_path=s_data['perception_output'].get('immediate_xml_path'),
            immediate_compressed_xml_path=s_data['perception_output'].get('immediate_compressed_xml_path'),
            immediate_compressed_txt_path=s_data['perception_output'].get('immediate_compressed_txt_path'),
            immediate_som_mapping_path=s_data['perception_output'].get('immediate_som_mapping_path')
        )

        # 重建path_from_root
        path_from_root = []
        for step_data in s_data['path_from_root']:
            step = PathStep(
                step_id=step_data['step_id'],
                instruction=step_data['instruction'],
                actions=step_data['actions'],
                from_state_id=step_data['from_state_id'],
                to_state_id=step_data['to_state_id'],
                from_state_name=step_data['from_state_name'],
                to_state_name=step_data['to_state_name'],
                success=step_data['success'],
                timestamp=step_data['timestamp']
            )
            path_from_root.append(step)

        state = PageState(
            state_id=sid,
            state_name=s_data['state_name'],
            activity_name=s_data['activity_name'],
            perception_output=perception_output,
            path_from_root=path_from_root,
            discovered_at=s_data['discovered_at'],
            reachable_states=s_data.get('reachable_states', [])
        )
        tree.states[sid] = state

    # 重建state_transitions
    for trans in data.get('state_transitions', []):
        tree.state_transitions.append((trans['from'], trans['to'], trans['step']))

    # 生成压缩版
    compressed_path = tree_path.parent / f"{tree_path.stem}_compressed{tree_path.suffix}"
    tree.save_to_file_compressed(compressed_path)

    # 统计对比
    import os
    original_size = os.path.getsize(tree_path)
    compressed_size = os.path.getsize(compressed_path)
    compression_ratio = (1 - compressed_size / original_size) * 100

    print(f"\n✅ 压缩完成！")
    print(f"  - 完整版: {tree_path.name} ({original_size / 1024:.1f}KB)")
    print(f"  - 压缩版: {compressed_path.name} ({compressed_size / 1024:.1f}KB)")
    print(f"  - 压缩率: {compression_ratio:.1f}%")
    print(f"  - 节省空间: {(original_size - compressed_size) / 1024:.1f}KB")

    # 分析step重复情况
    all_steps = {}
    total_step_references = 0
    for state in tree.states.values():
        total_step_references += len(state.path_from_root)
        for step in state.path_from_root:
            if step.step_id not in all_steps:
                all_steps[step.step_id] = 0
            all_steps[step.step_id] += 1

    print(f"\n📊 Step重复分析:")
    print(f"  - 唯一step数量: {len(all_steps)}")
    print(f"  - 总引用次数: {total_step_references}")
    print(f"  - 平均每个step被引用: {total_step_references / len(all_steps):.1f} 次")

    # 找出被引用最多的steps
    top_steps = sorted(all_steps.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"  - 被引用最多的steps:")
    for step_id, count in top_steps:
        print(f"    * {step_id}: {count}次")


if __name__ == "__main__":
    tree_path = Path("/Users/jackyyang/Desktop/毕业/论文/Fairy/integration/output/exploration/20251229_162639/feature_tree.json")

    if not tree_path.exists():
        print(f"❌ 文件不存在: {tree_path}")
    else:
        load_and_compress_tree(tree_path)
