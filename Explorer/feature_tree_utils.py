"""
功能树工具函数

提供压缩版feature_tree的还原、查询等功能
"""

import json
from pathlib import Path
from typing import Dict, List, Any


def load_compressed_tree(compressed_path: Path) -> Dict[str, Any]:
    """加载压缩版feature_tree

    Args:
        compressed_path: 压缩版feature_tree.json路径

    Returns:
        压缩版字典（包含顶层steps字典，states中path_from_root是step_id列表）
    """
    with open(compressed_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def expand_compressed_tree(compressed_data: Dict[str, Any]) -> Dict[str, Any]:
    """将压缩版feature_tree还原为完整版

    将states中的path_from_root从step_id列表还原为完整的step对象列表

    Args:
        compressed_data: 压缩版字典

    Returns:
        完整版字典（states中path_from_root包含完整step对象）
    """
    # 深拷贝以避免修改原数据
    import copy
    expanded = copy.deepcopy(compressed_data)

    # 获取steps字典
    steps = expanded.get('steps', {})

    # 遍历所有states，还原path_from_root
    for state_id, state in expanded['states'].items():
        # 从step_id列表还原为完整step对象列表
        step_ids = state['path_from_root']
        path_from_root = []

        for step_id in step_ids:
            if step_id in steps:
                path_from_root.append(steps[step_id])
            else:
                print(f"⚠️  警告: step_id '{step_id}' 在steps字典中不存在")

        state['path_from_root'] = path_from_root

    return expanded


def get_state_path(compressed_data: Dict[str, Any], state_id: str) -> List[Dict[str, Any]]:
    """获取到达某个state的完整路径（step序列）

    Args:
        compressed_data: 压缩版字典
        state_id: 状态ID

    Returns:
        完整的step对象列表
    """
    if state_id not in compressed_data['states']:
        raise ValueError(f"State '{state_id}' not found")

    state = compressed_data['states'][state_id]
    steps = compressed_data['steps']

    path = []
    for step_id in state['path_from_root']:
        if step_id in steps:
            path.append(steps[step_id])
        else:
            print(f"⚠️  警告: step_id '{step_id}' 在steps字典中不存在")

    return path


def get_feature_states(compressed_data: Dict[str, Any], feature_name: str) -> List[str]:
    """获取某个功能包含的所有状态ID

    Args:
        compressed_data: 压缩版字典
        feature_name: 功能名称

    Returns:
        状态ID列表
    """
    for feature in compressed_data['features'].values():
        if feature['feature_name'] == feature_name:
            return feature['states']

    raise ValueError(f"Feature '{feature_name}' not found")


def print_tree_summary(compressed_data: Dict[str, Any]):
    """打印feature_tree摘要信息

    Args:
        compressed_data: 压缩版字典
    """
    print("=" * 60)
    print("Feature Tree Summary")
    print("=" * 60)

    # 统计信息
    num_features = len(compressed_data['features'])
    num_states = len(compressed_data['states'])
    num_steps = len(compressed_data['steps'])
    num_transitions = len(compressed_data['state_transitions'])

    print(f"📊 基本统计:")
    print(f"  - 功能数量: {num_features}")
    print(f"  - 状态数量: {num_states}")
    print(f"  - 步骤数量: {num_steps}")
    print(f"  - 状态转换: {num_transitions}")

    # 功能列表
    print(f"\n🌳 功能列表:")
    for feature_id, feature in compressed_data['features'].items():
        status_icon = "✅" if feature['status'] == 'completed' else "🔄"
        print(f"  {status_icon} {feature['feature_name']} ({len(feature['states'])} 个状态)")
        if feature['feature_description']:
            print(f"     └─ {feature['feature_description']}")

    # Step引用统计
    print(f"\n📈 Step引用统计:")
    step_refs = {}
    for state in compressed_data['states'].values():
        for step_id in state['path_from_root']:
            step_refs[step_id] = step_refs.get(step_id, 0) + 1

    total_refs = sum(step_refs.values())
    avg_refs = total_refs / len(step_refs) if step_refs else 0
    print(f"  - 总引用次数: {total_refs}")
    print(f"  - 平均引用次数: {avg_refs:.1f}")

    top_steps = sorted(step_refs.items(), key=lambda x: x[1], reverse=True)[:3]
    print(f"  - 被引用最多的steps:")
    for step_id, count in top_steps:
        print(f"    * {step_id}: {count}次")

    print("=" * 60)


def visualize_feature_path(compressed_data: Dict[str, Any], state_id: str):
    """可视化到达某个state的路径

    Args:
        compressed_data: 压缩版字典
        state_id: 状态ID
    """
    if state_id not in compressed_data['states']:
        print(f"❌ State '{state_id}' not found")
        return

    state = compressed_data['states'][state_id]
    steps = compressed_data['steps']

    print("=" * 60)
    print(f"Path to State: {state['state_name']} ({state_id})")
    print("=" * 60)

    path = get_state_path(compressed_data, state_id)

    if not path:
        print("  (起始状态，无前置步骤)")
    else:
        for i, step in enumerate(path, 1):
            print(f"\n步骤 {i}: {step['step_id']}")
            print(f"  指令: {step['instruction']}")
            print(f"  从: {step['from_state_name']} ({step['from_state_id']})")
            print(f"  到: {step['to_state_name']} ({step['to_state_id']})")
            print(f"  结果: {'✅ 成功' if step['success'] else '❌ 失败'}")
            print(f"  时间: {step['timestamp']}")

    print("=" * 60)


if __name__ == "__main__":
    # 示例用法
    compressed_path = Path("/Users/jackyyang/Desktop/毕业/论文/Fairy/integration/output/exploration/20251229_162639/feature_tree_compressed.json")

    if compressed_path.exists():
        # 加载压缩版
        print("加载压缩版feature_tree...")
        data = load_compressed_tree(compressed_path)

        # 打印摘要
        print_tree_summary(data)

        # 可视化某个state的路径
        print("\n" + "=" * 60)
        visualize_feature_path(data, "state_main_bd3d23de")

        # 测试还原功能
        print("\n" + "=" * 60)
        print("测试还原功能...")
        expanded = expand_compressed_tree(data)

        # 验证还原
        state = expanded['states']['state_main_bd3d23de']
        print(f"✅ 还原后 path_from_root 长度: {len(state['path_from_root'])}")
        print(f"✅ 第一个step类型: {type(state['path_from_root'][0])}")
        print(f"✅ 第一个step内容: {list(state['path_from_root'][0].keys())}")
    else:
        print(f"❌ 文件不存在: {compressed_path}")
