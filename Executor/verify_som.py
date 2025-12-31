#!/usr/bin/env python3
"""
SoM标记验证脚本

用于诊断SoM标记和实际元素的对应关系
"""

import json
from pathlib import Path

def verify_som_mapping(som_mapping_file, compressed_txt_file):
    """验证SoM映射的正确性

    Args:
        som_mapping_file: som_mapping_XXX.json文件路径
        compressed_txt_file: compressed_XXX.txt文件路径
    """
    # 读取SoM映射
    with open(som_mapping_file, 'r') as f:
        som_mapping = json.load(f)

    # 读取压缩XML（包含元素中心坐标）
    with open(compressed_txt_file, 'r') as f:
        compressed_lines = f.readlines()

    # 解析元素和坐标（支持新格式：Mark N: ...）
    elements = {}  # 使用字典，key为mark编号
    for line in compressed_lines:
        line = line.strip()
        if not line:
            continue

        # 检查是否有标记编号
        mark_num = None
        if line.startswith('Mark ') and ':' in line:
            # 新格式: "Mark 14: FrameLayout ..."
            try:
                mark_part = line.split(':', 1)[0]
                mark_num = int(mark_part.replace('Mark', '').strip())
            except:
                pass

        # 解析中心坐标
        if '[Center: [' in line:
            try:
                center_str = line.split('[Center: [')[1].split(']')[0]
                x, y = map(float, center_str.split(','))

                # 提取类名
                class_name = ''
                if mark_num is not None:
                    # 新格式：Mark N: ClassName ...
                    parts = line.split(':', 1)[1].strip().split()
                    if parts:
                        class_name = parts[0]
                else:
                    # 旧格式：- ClassName ...
                    if line.startswith('- '):
                        parts = line[2:].split()
                        if parts:
                            class_name = parts[0]

                # 提取文本内容（在方括号中）
                text_parts = []
                import re
                text_matches = re.findall(r'\[(.*?)\]', line)
                for match in text_matches:
                    if not match.startswith('Center:') and not match.startswith('Bounds:') and ',' not in match:
                        text_parts.append(match)
                text = ' | '.join(text_parts) if text_parts else class_name

                elem_info = {
                    'mark_num': mark_num,
                    'text': text,
                    'class': class_name,
                    'center': (int(x), int(y)),
                    'line': line
                }

                if mark_num is not None:
                    elements[mark_num] = elem_info
                else:
                    # 旧格式，使用center作为临时key
                    elements[f"legacy_{len(elements)}"] = elem_info
            except Exception as e:
                # 解析失败，跳过
                pass

    print("=" * 80)
    print("SoM标记验证报告")
    print("=" * 80)
    print(f"\n解析到 {len(elements)} 个元素")
    print(f"SoM映射包含 {len(som_mapping)} 个标记")

    # 验证每个SoM标记
    print("\n## SoM标记 -> 元素映射")
    print("-" * 80)

    mismatches = []
    perfect_matches = 0
    close_matches = 0

    for mark, coord in sorted(som_mapping.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
        if isinstance(coord[0], list):
            # 滚动区域，跳过
            print(f"标记 {mark:>3}: 滚动区域 {coord}")
            continue

        mark_int = int(mark) if mark.isdigit() else None

        # 检查是否有完美匹配（索引直接对应）
        if mark_int is not None and mark_int in elements:
            elem = elements[mark_int]
            dist = ((coord[0] - elem['center'][0])**2 + (coord[1] - elem['center'][1])**2) ** 0.5

            if dist < 1:
                status = "✓ 完美匹配"
                perfect_matches += 1
            elif dist < 20:
                status = "✓"
                close_matches += 1
            else:
                status = "✗"
                mismatches.append({
                    'mark': mark,
                    'som_coord': coord,
                    'elem': elem,
                    'distance': dist
                })

            print(f"标记 {mark:>3}: {coord} -> {status} 距离 {dist:>5.1f}px -> {elem['text']}")
        else:
            # 没有直接匹配，找最接近的元素
            min_dist = float('inf')
            closest_elem = None

            for elem_key, elem in elements.items():
                dist = ((coord[0] - elem['center'][0])**2 + (coord[1] - elem['center'][1])**2) ** 0.5
                if dist < min_dist:
                    min_dist = dist
                    closest_elem = elem

            status = "✗ 索引不匹配"
            if closest_elem:
                if min_dist >= 20:
                    mismatches.append({
                        'mark': mark,
                        'som_coord': coord,
                        'elem': closest_elem,
                        'distance': min_dist
                    })

                print(f"标记 {mark:>3}: {coord} -> {status} 距离 {min_dist:>5.1f}px -> {closest_elem['text']}")
            else:
                print(f"标记 {mark:>3}: {coord} -> {status} 无匹配元素")

    print(f"\n{'=' * 80}")
    print(f"✓ 完美匹配: {perfect_matches} 个（距离 < 1px）")
    print(f"✓ 接近匹配: {close_matches} 个（距离 < 20px）")
    print(f"✗ 不匹配: {len(mismatches)} 个（距离 >= 20px 或索引不对应）")
    print(f"{'=' * 80}")

    # 报告不匹配的标记
    if mismatches:
        print("\n" + "=" * 80)
        print(f"⚠️  发现 {len(mismatches)} 个不匹配的标记（距离 >= 20px）")
        print("=" * 80)

        for m in mismatches:
            print(f"\n标记 {m['mark']}:")
            print(f"  SoM坐标: {m['som_coord']}")
            print(f"  最近元素: {m['elem']['text']}")
            print(f"  元素中心: {m['elem']['center']}")
            print(f"  距离: {m['distance']:.1f}px")
            print(f"  完整信息: {m['elem']['line']}")

    # 检查未标记的元素
    print("\n" + "=" * 80)
    print("## 检查索引覆盖率")
    print("-" * 80)

    marked_indices = set(int(mark) for mark in som_mapping.keys() if mark.isdigit() and not isinstance(som_mapping[mark][0], list))
    element_indices = set(elements.keys())

    unmarked_elements = element_indices - marked_indices
    if unmarked_elements:
        print(f"⚠️ 有 {len(unmarked_elements)} 个元素索引在SoM_mapping中缺失:")
        for idx in sorted(unmarked_elements):
            if idx in elements:
                elem = elements[idx]
                print(f"  Mark {idx}: {elem['text']} @ {elem['center']}")
    else:
        print("✓ 所有元素索引都在SoM_mapping中")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("用法: python verify_som.py <som_mapping.json> <compressed.txt>")
        print("\n示例:")
        print("  python verify_som.py step_6/stable/som_mapping_XXX.json step_6/stable/compressed_XXX.txt")
        sys.exit(1)

    verify_som_mapping(sys.argv[1], sys.argv[2])
