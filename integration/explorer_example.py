"""
Explorer 使用示例

演示如何使用 FairyExplorer 进行应用功能探索
"""

import asyncio
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from Explorer import (
    ExplorerConfig,
    FairyExplorer,
    ExplorationTarget,
    setup_logger
)


async def basic_exploration():
    """基础探索示例"""

    # 1. 配置日志
    setup_logger(
        log_level="INFO",
        log_file=Path("output/exploration/explorer.log"),
        enable_console=True,
        enable_file=True
    )

    # 2. 加载配置（从Explorer/.env）
    config = ExplorerConfig.from_env()
    print(f"\n配置信息:\n{config}\n")

    # 3. 创建Explorer
    explorer = FairyExplorer(config)

    # 4. 定义探索目标
    # target = ExplorationTarget(
    #     app_name="麦当劳",
    #     app_package="com.mcdonalds.gma.cn",  # 中国版麦当劳包名
    #     app_description="提供点餐、外卖、优惠券等功能的快餐连锁应用",
    #     feature_to_explore="麦乐送点餐功能。",
    #     starting_state="麦乐送界面"
    # )

    target = ExplorationTarget(
        app_name="Amaze",
        app_package="com.amaze.filemanager",  # 中国版麦当劳包名
        app_description="文件管理系统",
        feature_to_explore="文件（夹）复制剪切功能，测试复制（剪切）到不同层级文件夹的情况",
        starting_state="首页"
    )

    print(f"探索目标:")
    print(f"  应用: {target.app_name}")
    print(f"  功能: {target.feature_to_explore}")
    print()

    # 5. 执行探索
    result = await explorer.explore(target)

    # 6. 查看结果
    print("\n" + "=" * 60)
    print("探索结果:")
    print("=" * 60)
    print(f"成功: {result.success}")
    print(f"完成步骤: {result.completed_steps}/{result.total_steps}")
    print(f"失败步骤: {result.failed_steps}")
    print(f"总耗时: {result.total_time:.2f}秒")
    print(f"输出目录: {result.output_dir}")
    print()

    print("执行历史:")
    for i, snapshot in enumerate(result.execution_history, 1):
        print(f"  {i}. {snapshot.step_id}")
        print(f"     指令: {snapshot.executor_result.get('instruction', 'N/A')}")
        print(f"     成功: {snapshot.executor_result.get('success', False)}")
        print(f"     迭代次数: {snapshot.executor_result.get('iterations', 1)}")
        print()

    if result.execution_history:
        print("导航路径:")
        print(f"  {' -> '.join(result.execution_history[-1].navigation_path)}")
        print()
    else:
        print("导航路径: 无（未执行任何步骤）")
        print()

    if not result.success:
        print(f"错误: {result.error}")

    return result


async def custom_exploration():
    """自定义探索示例"""

    setup_logger(log_level="INFO")
    config = ExplorerConfig.from_env()

    # 修改配置
    config.max_exploration_steps = 10  # 限制最大步骤数
    config.replan_on_every_step = True  # 每步都重新规划

    explorer = FairyExplorer(config)

    # 自定义探索目标
    target = ExplorationTarget(
        app_name="应用名称",
        app_package="com.example.app",
        app_description="应用描述",
        feature_to_explore="要探索的功能描述",
        starting_state="首页"
    )

    result = await explorer.explore(target)

    print(f"探索完成: {result.success}")
    print(f"输出目录: {result.output_dir}")

    return result


if __name__ == "__main__":
    # 开始探索应用程序
    print("开始探索")
    asyncio.run(basic_exploration())

    # 或运行自定义示例
    # print("\n示例2: 自定义探索")
    # asyncio.run(custom_exploration())
