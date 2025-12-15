"""
反思循环示例

演示如何使用 FairyExecutor 的反思机制自动重复执行直到任务完成
"""

import asyncio
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from Executor import ExecutorConfig, FairyExecutor
from Executor.logger import setup_logger


async def reflection_example():
    """使用反思机制的示例"""

    # 配置日志
    setup_logger(log_level="INFO")

    # 加载配置
    config = ExecutorConfig.from_env()

    # 创建执行器
    executor = FairyExecutor(config)

    # ⭐ 执行需要多步完成的任务
    # 比如："向下滑动找到板烧鸡腿堡"
    # LLM会自动：
    # 1. 滑动一次
    # 2. 反思：看到板烧鸡腿堡了吗？
    # 3. 如果没看到，继续滑动
    # 4. 重复直到找到目标

    result = await executor.execute(
        instruction="向下滑动找到板烧鸡腿堡套餐",
        plan_context={
            "overall_plan": "浏览菜单并找到目标商品",
            "current_sub_goal": "找到板烧鸡腿堡套餐"
        },
        enable_reflection=True,  # ⭐ 启用反思
        max_iterations=5  # 最多尝试5次
    )

    # 查看结果
    print(f"\n=== 执行结果 ===")
    print(f"成功: {result.success}")
    print(f"迭代次数: {result.iterations}")
    print(f"执行时间: {result.execution_time:.2f}秒")
    print(f"执行的动作总数: {len(result.actions_taken)}")

    if result.progress_info:
        print(f"\n最终状态:")
        print(f"  结果: {result.progress_info.action_result}")
        print(f"  进度: {result.progress_info.progress_status}")
        if result.progress_info.error_potential_causes != "None":
            print(f"  错误: {result.progress_info.error_potential_causes}")

    return result


async def sequential_with_reflection():
    """顺序执行多个任务，每个任务都支持反思"""

    setup_logger(log_level="INFO")
    config = ExecutorConfig.from_env()
    executor = FairyExecutor(config)

    # 复杂的任务序列
    tasks = [
        {
            "instruction": "点击麦乐送",
            "sub_goal": "进入点餐界面",
            "enable_reflection": False  # 简单任务不需要反思
        },
        {
            "instruction": "点击鸡肉汉堡栏目",
            "sub_goal": "进入鸡肉汉堡分类",
            "enable_reflection": True
        },
        {
            "instruction": "找到板烧鸡腿堡套餐",
            "sub_goal": "找到板烧鸡腿堡套餐",
            "enable_reflection": True,  # ⭐ 需要多次滑动的任务启用反思
            "max_iterations": 5
        },
        {
            "instruction": "将板烧鸡腿堡套餐加入购物车",
            "sub_goal": "加入购物车",
            "enable_reflection": True,  # 可能需要多步操作
            "max_iterations": 3
        },
        {
            "instruction": "点击结算按钮",
            "sub_goal": "进行结算",
            "enable_reflection": False
        }
    ]

    results = []

    for i, task in enumerate(tasks, 1):
        print(f"\n{'='*60}")
        print(f"任务 {i}/{len(tasks)}: {task['instruction']}")
        print(f"{'='*60}")

        result = await executor.execute(
            instruction=task['instruction'],
            plan_context={
                "overall_plan": "完成麦当劳点餐流程",
                "current_sub_goal": task['sub_goal']
            },
            enable_reflection=task.get('enable_reflection', False),
            max_iterations=task.get('max_iterations', 1)
        )

        results.append(result)

        print(f"\n任务 {i} 结果:")
        print(f"  成功: {result.success}")
        print(f"  迭代次数: {result.iterations}")

        if not result.success:
            print(f"  ✗ 任务失败: {result.error}")
            break
        else:
            print(f"  ✓ 任务完成")

    # 汇总
    print(f"\n{'='*60}")
    print(f"总结:")
    print(f"  完成任务数: {len([r for r in results if r.success])}/{len(tasks)}")
    print(f"  总迭代次数: {sum(r.iterations for r in results)}")
    print(f"  总执行时间: {sum(r.execution_time for r in results):.2f}秒")

    return results


async def disable_reflection_example():
    """不使用反思的示例（与之前行为一致）"""

    setup_logger(log_level="INFO")
    config = ExecutorConfig.from_env()
    executor = FairyExecutor(config)

    # 简单任务，不需要反思
    result = await executor.execute(
        instruction="点击游戏按钮",
        enable_reflection=False  # ⭐ 禁用反思，执行一次就退出
    )

    print(f"执行结果: {result.success}")
    print(f"迭代次数: {result.iterations}")  # 应该是1

    return result


if __name__ == "__main__":
    # 运行反思示例
    # print("示例1: 使用反思机制")
    # asyncio.run(reflection_example())

    # 运行复杂序列
    print("\n示例2: 复杂任务序列")
    asyncio.run(sequential_with_reflection())

    # 运行无反思示例
    # print("\n示例3: 禁用反思（传统模式）")
    # asyncio.run(disable_reflection_example())
