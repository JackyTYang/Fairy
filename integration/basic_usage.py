"""
基本使用示例

演示如何使用FairyExecutor执行简单的移动端自动化任务
"""

import asyncio
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fairy_executor import ExecutorConfig, FairyExecutor
from fairy_executor.logger import setup_logger


async def basic_example():
    """基本使用示例"""

    # 1. 配置日志
    setup_logger(
        log_level="INFO",
        log_file=Path("output/logs/basic_example.log"),
        enable_console=True,
        enable_file=True
    )

    # 2. 从环境变量加载配置
    config = ExecutorConfig.from_env()

    # 3. 创建执行器
    executor = FairyExecutor(config)

    # 4. 执行单个指令
    result = await executor.execute(
        instruction="点击游戏按钮",
        plan_context={
            "overall_plan": "进入游戏页面",
            "current_sub_goal": "点击游戏按钮"
        }
    )

    # 5. 查看结果
    print(f"\n执行结果:")
    print(f"  成功: {result.success}")
    print(f"  执行时间: {result.execution_time:.2f}秒")
    print(f"  执行的动作: {result.actions_taken}")
    print(f"  动作思考: {result.action_thought}")
    print(f"  预期结果: {result.action_expectation}")
    print(f"\n输出文件:")
    for key, path in result.output_files.items():
        print(f"  {key}: {path}")

    # 6. 获取会话摘要
    summary = executor.get_session_summary()
    print(f"\n会话摘要:")
    print(f"  会话ID: {summary['session_id']}")
    print(f"  执行次数: {summary['execution_count']}")
    print(f"  截图数量: {summary['screenshots_count']}")

    return result


async def sequential_execution():
    """顺序执行多个指令"""

    setup_logger(log_level="INFO")
    config = ExecutorConfig.from_env()
    executor = FairyExecutor(config)

    # 执行一系列指令
    instructions = [
        # ("点击麦乐送", "进入点餐界面"),
        # ("点击鸡肉汉堡栏目", "进入鸡肉汉堡界面"),
        ("向下滑动", "找到板烧鸡腿堡套餐"),
        ("将板烧鸡腿堡套餐加入购物车", "加入购物车"),
        ("点击结算按钮", "进行结算")
    ]

    results = []
    historical_actions = []

    for instruction, sub_goal in instructions:
        print(f"\n执行: {instruction}")

        result = await executor.execute(
            instruction=instruction,
            plan_context={
                "overall_plan": "浏览游戏列表",
                "current_sub_goal": sub_goal
            },
            historical_actions=historical_actions
        )

        results.append(result)

        if result.success:
            historical_actions.extend(result.actions_taken)
            print(f"✓ 成功: {result.action_expectation}")
        else:
            print(f"✗ 失败: {result.error}")
            break

    return results


async def with_execution_tips():
    """使用执行建议"""

    setup_logger(log_level="INFO")
    config = ExecutorConfig.from_env()
    executor = FairyExecutor(config)

    # 提供执行建议（可以从RAG系统获取）
    tips = """
    - 游戏按钮通常在底部导航栏
    - 如果看不到目标元素，尝试向下滚动
    - 点击前确认元素可见且可点击
    """

    result = await executor.execute(
        instruction="点击游戏按钮",
        execution_tips=tips
    )

    return result


if __name__ == "__main__":
    # 运行基本示例
    # asyncio.run(basic_example())

    # 或运行其他示例
    asyncio.run(sequential_execution())
    # asyncio.run(with_execution_tips())
