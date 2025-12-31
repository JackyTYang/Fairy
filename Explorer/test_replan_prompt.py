#!/usr/bin/env python3
"""
测试新旧 replan prompt 的对比
使用真实的探索数据进行对比
"""

import sys
import json
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from Explorer.config import ExplorerConfig
from Explorer.planner import ExplorationPlanner
from Explorer.entities import ExplorationTarget, ExplorationPlan, ExplorationStep, PerceptionOutput

def load_test_data():
    """加载 step_11 的真实测试数据"""
    base_dir = Path("/Users/jackyyang/Desktop/毕业/论文/Fairy/integration/output/exploration/20251228_184612")

    # 加载计划
    plan_file = base_dir / "plan_after_step_step_11.json"
    with open(plan_file, 'r', encoding='utf-8') as f:
        plan_data = json.load(f)

    # 构建 ExplorationPlan
    steps = [
        ExplorationStep(
            step_id=s['step_id'],
            instruction=s['instruction'],
            sub_goal=s['sub_goal'],
            status=s.get('status', 'pending'),
            enable_reflection=s.get('enable_reflection', True),
            max_iterations=s.get('max_iterations', 5)
        )
        for s in plan_data['steps']
    ]

    current_plan = ExplorationPlan(
        plan_thought=plan_data.get('plan_thought', ''),
        overall_plan=plan_data.get('overall_plan', ''),
        steps=steps,
        pending_steps=[s.step_id for s in steps if s.status == 'pending'],
        completed_steps=plan_data.get('completed_steps', []),
        feature_structure=plan_data.get('feature_structure', {}),
        current_feature=plan_data.get('current_feature', {}),
        feature_update=plan_data.get('feature_update')
    )

    # 构建 ExplorationTarget
    target = ExplorationTarget(
        app_name="Amaze文件管理器",
        app_package="com.amaze.filemanager",
        app_description="开源文件管理应用",
        feature_to_explore="文件（夹）创建删除复制剪切重命名等功能",
        starting_state="首页"
    )

    # 构建最后一步
    last_step = steps[0]  # step_11

    # 构建最后执行结果
    last_result = {
        'success': True,
        'iterations': 1,
        'execution_time': 27.44
    }

    # 构建当前 perception
    step11_dir = base_dir / "step_11" / "stable"

    # 读取屏幕文本
    compressed_txt = step11_dir / "compressed_1766919225.txt"
    with open(compressed_txt, 'r', encoding='utf-8') as f:
        screen_text = f.read()

    # 构建 PerceptionOutput
    current_perception = PerceptionOutput(
        screenshot_path=str(step11_dir / "screenshot_1766919225.jpeg"),
        marked_screenshot_path=str(step11_dir / "screenshot_1766919225_marked.jpeg"),
        xml_path=str(step11_dir / "ui_dump_1766919225.xml"),
        compressed_xml_path=str(step11_dir / "compressed_1766919225.xml"),
        compressed_txt_path=str(compressed_txt),
        som_mapping_path=str(step11_dir / "som_mapping_1766919225.json"),
        timestamp="1766919225",
        screen_size=(1080, 2400),
        immediate_screenshot_path=None,  # 单截图模式
        immediate_marked_screenshot_path=None,
        immediate_xml_path=None,
        immediate_compressed_xml_path=None,
        immediate_compressed_txt_path=None,
        immediate_som_mapping_path=None
    )

    # 导航路径
    navigation_path = [
        "首页",
        "在新建对话框中完成名称输入，输入框显示\"test_new_item\"。",
        "提交名称 test_new_item 并完成新建文件夹操作，关闭对话框并返回文件列表界面。",
        # ... 其他路径
    ]

    return {
        'target': target,
        'current_plan': current_plan,
        'screen_text': screen_text,
        'last_step': last_step,
        'last_result': last_result,
        'current_perception': current_perception,
        'navigation_path': navigation_path
    }


def test_original_prompt():
    """测试原版 prompt"""
    print("=" * 80)
    print("测试原版 Replan Prompt")
    print("=" * 80)

    # 加载配置和数据
    config = ExplorerConfig(
        llm_model_name="gpt-4o",
        llm_api_key="dummy",
        llm_api_base="https://api.openai.com/v1",
        visual_model_name="gpt-4o",
        visual_api_key="dummy",
        visual_api_base="https://api.openai.com/v1",
        adb_path="/usr/local/bin/adb"
    )

    # ⭐ 不完整初始化，只需要 config 和 _get_app_specific_tips 方法
    # 创建一个最小化的 mock planner
    class MockPlanner:
        def __init__(self, config):
            self.config = config
            from tips_loader import get_tips_loader
            self.tips_loader = get_tips_loader()

        def _get_app_specific_tips(self, target):
            tips = self.tips_loader.get_tips_for_app(
                app_package=target.app_package,
                app_name=target.app_name
            )
            return tips if tips else ""

    planner = MockPlanner(config)

    # 导入并绑定原版方法
    from planner import ExplorationPlanner
    planner._build_replan_prompt = ExplorationPlanner._build_replan_prompt.__get__(planner, MockPlanner)
    data = load_test_data()

    # 构建 prompt（使用原版方法）
    prompt = planner._build_replan_prompt(
        target=data['target'],
        current_plan=data['current_plan'],
        screen_text=data['screen_text'],
        last_step=data['last_step'],
        last_result=data['last_result'],
        navigation_path=data['navigation_path'],
        immediate_screen_text=None,
        feature_tree=None,
        recent_state_sequence=None
    )

    # 保存到文件
    output_file = Path(__file__).parent / "test_output_original_prompt.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(prompt)

    # 统计信息
    line_count = len(prompt.split('\n'))
    char_count = len(prompt)

    # 估算token数（粗略：中文1字≈1.5token，英文1词≈1token）
    # 简化计算：总字符数 / 3
    estimated_tokens = char_count // 3

    print(f"✅ 原版 Prompt 已保存到: {output_file}")
    print(f"📊 统计信息:")
    print(f"   - 总行数: {line_count}")
    print(f"   - 总字符数: {char_count}")
    print(f"   - 估算tokens: ~{estimated_tokens}")
    print()


def test_new_prompt():
    """测试新版 prompt"""
    print("=" * 80)
    print("测试新版 Replan Prompt")
    print("=" * 80)

    # 导入新版本的函数
    from planner_prompt_replan_new import _build_replan_prompt_optimized

    config = ExplorerConfig(
        llm_model_name="gpt-4o",
        llm_api_key="dummy",
        llm_api_base="https://api.openai.com/v1",
        visual_model_name="gpt-4o",
        visual_api_key="dummy",
        visual_api_base="https://api.openai.com/v1",
        adb_path="/usr/local/bin/adb"
    )

    # ⭐ 创建最小化的 mock planner（同原版测试）
    class MockPlanner:
        def __init__(self, config):
            self.config = config
            from tips_loader import get_tips_loader
            self.tips_loader = get_tips_loader()

        def _get_app_specific_tips(self, target):
            tips = self.tips_loader.get_tips_for_app(
                app_package=target.app_package,
                app_name=target.app_name
            )
            return tips if tips else ""

    planner = MockPlanner(config)
    data = load_test_data()

    # 使用新版函数
    prompt = _build_replan_prompt_optimized(
        planner,
        target=data['target'],
        current_plan=data['current_plan'],
        screen_text=data['screen_text'],
        last_step=data['last_step'],
        last_result=data['last_result'],
        navigation_path=data['navigation_path'],
        immediate_screen_text=None,
        feature_tree=None,
        recent_state_sequence=None
    )

    # 保存到文件
    output_file = Path(__file__).parent / "test_output_new_prompt.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(prompt)

    # 统计信息
    line_count = len(prompt.split('\n'))
    char_count = len(prompt)
    estimated_tokens = char_count // 3

    print(f"✅ 新版 Prompt 已保存到: {output_file}")
    print(f"📊 统计信息:")
    print(f"   - 总行数: {line_count}")
    print(f"   - 总字符数: {char_count}")
    print(f"   - 估算tokens: ~{estimated_tokens}")
    print()


def compare_prompts():
    """对比两个版本"""
    print("=" * 80)
    print("对比分析")
    print("=" * 80)

    original_file = Path(__file__).parent / "test_output_original_prompt.txt"
    new_file = Path(__file__).parent / "test_output_new_prompt.txt"

    if not original_file.exists():
        print("❌ 原版输出文件不存在，请先运行 test_original_prompt()")
        return

    if not new_file.exists():
        print("❌ 新版输出文件不存在，请先运行 test_new_prompt()")
        return

    with open(original_file, 'r', encoding='utf-8') as f:
        original = f.read()

    with open(new_file, 'r', encoding='utf-8') as f:
        new = f.read()

    orig_lines = len(original.split('\n'))
    new_lines = len(new.split('\n'))

    orig_chars = len(original)
    new_chars = len(new)

    orig_tokens = orig_chars // 3
    new_tokens = new_chars // 3

    print(f"📊 对比结果:")
    print(f"   行数:    {orig_lines:5d} → {new_lines:5d} (变化: {new_lines - orig_lines:+d}, {(new_lines - orig_lines) / orig_lines * 100:+.1f}%)")
    print(f"   字符数:  {orig_chars:5d} → {new_chars:5d} (变化: {new_chars - orig_chars:+d}, {(new_chars - orig_chars) / orig_chars * 100:+.1f}%)")
    print(f"   估算tokens: {orig_tokens:5d} → {new_tokens:5d} (变化: {new_tokens - orig_tokens:+d}, {(new_tokens - orig_tokens) / orig_tokens * 100:+.1f}%)")
    print()
    print(f"💾 使用 diff 工具对比两个文件:")
    print(f"   diff {original_file} {new_file}")
    print(f"   或使用 VS Code: code -d {original_file} {new_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="测试 replan prompt 新旧版本对比")
    parser.add_argument('--mode', choices=['original', 'new', 'compare', 'all'],
                        default='all', help='测试模式')

    args = parser.parse_args()

    if args.mode in ['original', 'all']:
        test_original_prompt()

    if args.mode in ['new', 'all']:
        try:
            test_new_prompt()
        except Exception as e:
            print(f"❌ 新版测试失败: {e}")
            print("提示: 请确保 planner_prompt_replan_new.py 中的函数正确实现")

    if args.mode in ['compare', 'all']:
        compare_prompts()
