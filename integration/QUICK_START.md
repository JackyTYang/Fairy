# Fairy Executor 快速开始

5分钟快速上手指南。

## 安装

```bash
# 安装依赖
pip install loguru python-dotenv

# 可选：LangGraph集成
pip install langgraph langchain-core
```

## 配置

创建 `.env` 文件：

```bash
# 设备
DEVICE_ID=emulator-5554

# 核心LLM
CORE_LMM_MODEL_NAME=gpt-4o-2024-11-20
CORE_LMM_API_KEY=sk-...
CORE_LMM_API_BASE=https://api.openai.com/v1

# 视觉模型
VISUAL_PROMPT_LMM_API_NAME=qwen-vl-plus
VISUAL_PROMPT_LMM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
VISUAL_PROMPT_LMM_API_KEY=sk-...

# 文本模型
RAG_LLM_API_NAME=qwen-turbo-0428
RAG_LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
RAG_LLM_API_KEY=sk-...
```

## 基本使用

```python
import asyncio
from fairy_executor import ExecutorConfig, FairyExecutor
from fairy_executor.logger import setup_logger

async def main():
    # 1. 配置日志
    setup_logger(log_level="INFO")

    # 2. 加载配置
    config = ExecutorConfig.from_env()

    # 3. 创建执行器
    executor = FairyExecutor(config)

    # 4. 执行指令
    result = await executor.execute("点击游戏按钮")

    # 5. 查看结果
    print(f"成功: {result.success}")
    print(f"动作: {result.actions_taken}")

asyncio.run(main())
```

## 常用场景

### 场景1: 顺序执行多个指令

```python
executor = FairyExecutor(config)
historical_actions = []

instructions = ["点击游戏", "向下滚动", "点击第一个游戏"]

for instruction in instructions:
    result = await executor.execute(
        instruction=instruction,
        historical_actions=historical_actions
    )

    if result.success:
        historical_actions.extend(result.actions_taken)
```

### 场景2: 使用计划上下文

```python
result = await executor.execute(
    instruction="点击游戏按钮",
    plan_context={
        "overall_plan": "测试游戏页面功能",
        "current_sub_goal": "进入游戏页面"
    }
)
```

### 场景3: 使用执行建议

```python
result = await executor.execute(
    instruction="点击游戏按钮",
    execution_tips="游戏按钮通常在底部导航栏"
)
```

### 场景4: 查看输出文件

```python
result = await executor.execute("点击游戏")

# 查看所有输出文件
for key, path in result.output_files.items():
    print(f"{key}: {path}")

# 输出:
# screenshot_before: output/.../exec_001_before.jpg
# screenshot_after: output/.../exec_001_after.jpg
# marked_image_before: output/.../exec_001_before_marked.jpg
# result: output/.../result.json
```

### 场景5: 保存结果

```python
result = await executor.execute("点击游戏")

# 保存为JSON
result.save_to_file(Path("my_result.json"))

# 或转换为字典
result_dict = result.to_dict()
```

## LangGraph集成

```python
from langgraph.graph import StateGraph
from fairy_executor import FairyExecutor

class TestAgent:
    def __init__(self, executor: FairyExecutor):
        self.executor = executor

    async def execute_node(self, state):
        result = await self.executor.execute(
            instruction=state["instruction"]
        )
        state["results"].append(result)
        return state

# 构建工作流
workflow = StateGraph(AgentState)
workflow.add_node("execute", agent.execute_node)
graph = workflow.compile()

# 运行
final_state = await graph.ainvoke(initial_state)
```

## 调试技巧

### 1. 启用详细日志

```python
setup_logger(
    log_level="DEBUG",
    log_file=Path("logs/debug.log")
)
```

### 2. 查看标记图像

```python
result = await executor.execute("点击游戏")

# 标记图像路径
marked_image = result.output_files['marked_image_before']
print(f"标记图像: {marked_image}")

# 在macOS上打开
import subprocess
subprocess.run(['open', marked_image])
```

### 3. 分析LLM决策

```python
result = await executor.execute("点击游戏")

print(f"LLM思考: {result.action_thought}")
print(f"决策动作: {result.actions_taken}")
print(f"预期结果: {result.action_expectation}")
```

## 常见问题

### Q: 点击位置不准确？

确保配置了视觉模型并启用Set-of-Marks模式：

```bash
# .env
VISUAL_PROMPT_LMM_API_NAME=qwen-vl-plus
NON_VISUAL_MODE=False  # 启用Set-of-Marks
```

### Q: 如何查看执行历史？

```python
summary = executor.get_session_summary()
print(summary)
# {
#     'session_id': '20231210_143022',
#     'execution_count': 5,
#     'screenshots_count': 10
# }
```

### Q: 如何自定义输出目录？

```python
config = ExecutorConfig.from_env()
config.output.output_dir = Path("my_output")
executor = FairyExecutor(config)
```

## 完整示例

查看完整示例代码：

- `integration/basic_usage.py` - 基本使用
- `integration/langgraph_integration.py` - LangGraph集成

## 更多文档

- [模块文档](fairy_executor/README.md) - 完整API参考
- [集成指南](integration/README.md) - 集成场景和最佳实践
- [迁移指南](MIGRATION_GUIDE.md) - 从旧版本迁移
- [重构总结](REFACTORING_SUMMARY.md) - 架构和设计说明

## 下一步

1. 运行示例代码：`python integration/basic_usage.py`
2. 阅读完整文档：`fairy_executor/README.md`
3. 尝试集成到你的项目中

祝你使用愉快！🎉
