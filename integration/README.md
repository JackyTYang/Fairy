# Fairy Executor 集成指南

本目录包含将Fairy Executor集成到不同框架和场景的示例代码。

## 目录结构

```
integration/
├── README.md                    # 本文件
├── basic_usage.py              # 基本使用示例
└── langgraph_integration.py    # LangGraph集成示例
```

## 快速开始

### 1. 基本使用

最简单的使用方式：

```bash
python integration/basic_usage.py
```

这个示例展示了：
- 如何配置和初始化执行器
- 如何执行单个指令
- 如何顺序执行多个指令
- 如何使用执行建议

### 2. LangGraph集成

如果你想使用LangGraph编排测试流程：

```bash
# 安装依赖
pip install langgraph langchain-core

# 运行示例
python integration/langgraph_integration.py
```

这个示例展示了：
- 如何将FairyExecutor集成到LangGraph工作流
- 如何构建自动化测试Agent
- 如何使用状态管理和条件分支

## 集成场景

### 场景1: 自动化测试框架

将Fairy Executor作为执行引擎，集成到自动化测试框架中。

**适用于:**
- UI自动化测试
- 回归测试
- 冒烟测试

**示例:**

```python
from fairy_executor import ExecutorConfig, FairyExecutor

class MobileTestFramework:
    def __init__(self):
        config = ExecutorConfig.from_env()
        self.executor = FairyExecutor(config)

    async def run_test_case(self, test_case):
        """运行单个测试用例"""
        results = []

        for step in test_case.steps:
            result = await self.executor.execute(
                instruction=step.instruction,
                plan_context={
                    "overall_plan": test_case.name,
                    "current_sub_goal": step.name
                }
            )

            results.append(result)

            # 验证结果
            if not step.verify(result):
                return TestResult(
                    passed=False,
                    failed_step=step.name,
                    results=results
                )

        return TestResult(passed=True, results=results)
```

### 场景2: LangGraph工作流

使用LangGraph编排复杂的测试流程。

**适用于:**
- 多步骤测试流程
- 需要条件分支的测试
- 需要状态管理的测试

**示例:**

```python
from langgraph.graph import StateGraph, END
from fairy_executor import FairyExecutor

class TestAgent:
    def __init__(self, executor: FairyExecutor):
        self.executor = executor

    def build_graph(self):
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("plan", self.plan_node)
        workflow.add_node("execute", self.execute_node)
        workflow.add_node("verify", self.verify_node)

        # 添加边
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "execute")
        workflow.add_conditional_edges(
            "verify",
            self.should_continue,
            {"continue": "execute", "end": END}
        )

        return workflow.compile()
```

### 场景3: 自定义Agent系统

构建自己的Agent系统，使用Fairy Executor作为执行模块。

**适用于:**
- 自定义的Agent架构
- 需要特殊逻辑的测试场景
- 研究和实验

**示例:**

```python
from fairy_executor import FairyExecutor

class CustomAgent:
    def __init__(self, executor: FairyExecutor):
        self.executor = executor
        self.memory = []

    async def execute_with_memory(self, instruction):
        """执行指令并记录到记忆中"""
        result = await self.executor.execute(
            instruction=instruction,
            historical_actions=[
                action
                for memory in self.memory
                for action in memory.actions_taken
            ]
        )

        self.memory.append(result)
        return result

    async def execute_with_retry(self, instruction, max_retries=3):
        """执行指令，失败时重试"""
        for attempt in range(max_retries):
            result = await self.executor.execute(instruction)

            if result.success:
                return result

            # 分析失败原因并调整策略
            if "找不到元素" in result.error:
                # 尝试滚动后重试
                await self.executor.execute("向下滚动")

        return result
```

### 场景4: RAG增强执行

结合RAG系统提供执行建议。

**适用于:**
- 需要领域知识的测试
- 复杂应用的测试
- 需要历史经验的测试

**示例:**

```python
from fairy_executor import FairyExecutor

class RAGEnhancedExecutor:
    def __init__(self, executor: FairyExecutor, rag_system):
        self.executor = executor
        self.rag_system = rag_system

    async def execute_with_rag(self, instruction, app_name):
        """使用RAG系统提供执行建议"""

        # 从RAG系统检索相关建议
        tips = self.rag_system.retrieve(
            query=instruction,
            filters={"app_name": app_name}
        )

        # 执行指令
        result = await self.executor.execute(
            instruction=instruction,
            execution_tips=tips
        )

        # 如果成功，将经验存入RAG
        if result.success:
            self.rag_system.store(
                instruction=instruction,
                actions=result.actions_taken,
                app_name=app_name
            )

        return result
```

## 配置最佳实践

### 1. 环境变量管理

使用不同的 `.env` 文件管理不同环境：

```bash
# .env.dev - 开发环境
DEVICE_ID=emulator-5554
LOG_LEVEL=DEBUG

# .env.prod - 生产环境
DEVICE_ID=real-device-id
LOG_LEVEL=INFO
```

加载配置：

```python
config = ExecutorConfig.from_env(env_file=".env.dev")
```

### 2. 日志配置

为不同场景配置不同的日志级别：

```python
from fairy_executor.logger import setup_logger

# 开发环境：详细日志
setup_logger(
    log_level="DEBUG",
    log_file=Path("logs/dev.log")
)

# 生产环境：简洁日志
setup_logger(
    log_level="INFO",
    log_file=Path("logs/prod.log")
)
```

### 3. 输出管理

自定义输出目录结构：

```python
from datetime import datetime

config = ExecutorConfig.from_env()
config.output.output_dir = Path(f"test_results/{datetime.now():%Y%m%d}")
```

## 性能优化

### 1. 复用执行器实例

```python
# ✓ 好的做法：复用实例
executor = FairyExecutor(config)
for instruction in instructions:
    await executor.execute(instruction)

# ✗ 不好的做法：每次创建新实例
for instruction in instructions:
    executor = FairyExecutor(config)  # 重复初始化
    await executor.execute(instruction)
```

### 2. 批量执行

```python
async def batch_execute(executor, instructions):
    """批量执行指令"""
    results = []
    historical_actions = []

    for instruction in instructions:
        result = await executor.execute(
            instruction=instruction,
            historical_actions=historical_actions
        )

        results.append(result)
        if result.success:
            historical_actions.extend(result.actions_taken)

    return results
```

### 3. 并发执行（多设备）

```python
import asyncio

async def parallel_test(devices, test_case):
    """在多个设备上并行执行测试"""
    tasks = []

    for device_id in devices:
        config = ExecutorConfig.from_env()
        config.device.device_id = device_id
        executor = FairyExecutor(config)

        task = executor.execute(test_case.instruction)
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results
```

## 错误处理

### 1. 基本错误处理

```python
result = await executor.execute("点击游戏")

if not result.success:
    print(f"执行失败: {result.error}")
    # 处理错误...
```

### 2. 重试机制

```python
async def execute_with_retry(executor, instruction, max_retries=3):
    """带重试的执行"""
    for attempt in range(max_retries):
        result = await executor.execute(instruction)

        if result.success:
            return result

        print(f"尝试 {attempt + 1} 失败，重试...")
        await asyncio.sleep(1)

    return result
```

### 3. 异常捕获

```python
try:
    result = await executor.execute("点击游戏")
except Exception as e:
    print(f"执行异常: {e}")
    # 记录日志、发送告警等
```

## 调试技巧

### 1. 查看标记图像

```python
result = await executor.execute("点击游戏")

# 查看标记图像路径
marked_image = result.output_files.get('marked_image_before')
print(f"标记图像: {marked_image}")

# 使用图像查看器打开
import subprocess
subprocess.run(['open', marked_image])  # macOS
```

### 2. 分析LLM决策

```python
result = await executor.execute("点击游戏")

print(f"LLM思考: {result.action_thought}")
print(f"决策动作: {result.actions_taken}")
print(f"预期结果: {result.action_expectation}")
```

### 3. 查看执行日志

```python
# 设置DEBUG级别
setup_logger(log_level="DEBUG")

# 执行后查看日志文件
# logs/fairy_executor.log
```

## 常见问题

### Q: 如何在pytest中使用？

```python
import pytest
from fairy_executor import ExecutorConfig, FairyExecutor

@pytest.fixture(scope="session")
async def executor():
    config = ExecutorConfig.from_env()
    return FairyExecutor(config)

@pytest.mark.asyncio
async def test_game_page(executor):
    result = await executor.execute("点击游戏按钮")
    assert result.success
    assert "游戏" in result.action_expectation
```

### Q: 如何集成到CI/CD？

```yaml
# .github/workflows/test.yml
name: Mobile UI Tests

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Setup Android Emulator
        uses: reactivecircus/android-emulator-runner@v2

      - name: Run Tests
        env:
          DEVICE_ID: emulator-5554
          CORE_LMM_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python integration/basic_usage.py
```

### Q: 如何处理不同的应用？

```python
# 为不同应用创建不同的配置
configs = {
    "game_app": {
        "tips": "游戏按钮在底部导航栏",
        "timeout": 10
    },
    "shopping_app": {
        "tips": "商品列表需要向下滚动",
        "timeout": 5
    }
}

async def execute_for_app(executor, app_name, instruction):
    app_config = configs[app_name]

    result = await executor.execute(
        instruction=instruction,
        execution_tips=app_config["tips"]
    )

    return result
```

## 更多资源

- [Fairy Executor README](../fairy_executor/README.md) - 模块文档
- [CLAUDE.md](../CLAUDE.md) - 项目架构说明
- [基本使用示例](basic_usage.py) - 完整代码
- [LangGraph集成示例](langgraph_integration.py) - 完整代码

## 贡献

欢迎提交问题和改进建议！
