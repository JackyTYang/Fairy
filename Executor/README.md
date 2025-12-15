# Fairy Executor

模块化的移动端自动化执行器，从Fairy项目中提取并重构。

## 特性

- ✅ **独立运行**：不依赖Citlali框架，可独立使用
- ✅ **清晰配置**：统一的配置管理，支持环境变量、字典、文件加载
- ✅ **标准日志**：使用loguru提供美观的日志输出
- ✅ **输出管理**：自动保存截图、标记图像、执行结果
- ✅ **易于集成**：可轻松集成到LangGraph等框架中
- ✅ **Set-of-Marks**：支持视觉标记模式，提高点击准确性

## 快速开始

### 安装依赖

```bash
pip install loguru python-dotenv
```

### 基本使用

```python
import asyncio
from fairy_executor import ExecutorConfig, FairyExecutor
from fairy_executor.logger import setup_logger

async def main():
    # 1. 配置日志
    setup_logger(log_level="INFO")

    # 2. 从环境变量加载配置
    config = ExecutorConfig.from_env()

    # 3. 创建执行器
    executor = FairyExecutor(config)

    # 4. 执行指令
    result = await executor.execute(
        instruction="点击游戏按钮",
        plan_context={
            "overall_plan": "进入游戏页面",
            "current_sub_goal": "点击游戏按钮"
        }
    )

    # 5. 查看结果
    print(f"成功: {result.success}")
    print(f"执行的动作: {result.actions_taken}")
    print(f"输出文件: {result.output_files}")

asyncio.run(main())
```

## 配置

### 环境变量配置

在 `.env` 文件中配置：

```bash
# 设备配置
DEVICE_ID=emulator-5554

# 核心LLM（用于动作决策）
CORE_LMM_MODEL_NAME=gpt-4o-2024-11-20
CORE_LMM_API_KEY=sk-...
CORE_LMM_API_BASE=https://api.openai.com/v1

# 视觉模型（用于屏幕理解）
VISUAL_PROMPT_LMM_API_NAME=qwen-vl-plus
VISUAL_PROMPT_LMM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
VISUAL_PROMPT_LMM_API_KEY=sk-...

# 文本摘要模型
RAG_LLM_API_NAME=qwen-turbo-0428
RAG_LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
RAG_LLM_API_KEY=sk-...

# 输出配置
OUTPUT_DIR=output
LOG_LEVEL=INFO
NON_VISUAL_MODE=False  # False=使用Set-of-Marks标记模式
```

### 代码配置

```python
from fairy_executor import ExecutorConfig, ModelConfig, DeviceConfig

# 方式1: 从环境变量
config = ExecutorConfig.from_env()

# 方式2: 从字典
config = ExecutorConfig.from_dict({
    'device': {'device_id': 'emulator-5554'},
    'core_model': {
        'model_name': 'gpt-4o',
        'api_key': 'sk-...',
        'api_base': 'https://api.openai.com/v1'
    }
})

# 方式3: 直接构造
config = ExecutorConfig(
    device=DeviceConfig(device_id='emulator-5554'),
    core_model=ModelConfig(
        model_name='gpt-4o',
        api_key='sk-...',
        api_base='https://api.openai.com/v1'
    ),
    perception=PerceptionConfig.from_env(),
    output=OutputConfig(output_dir='output')
)
```

## API参考

### FairyExecutor

主执行器类。

#### `__init__(config: ExecutorConfig)`

初始化执行器。

**参数:**
- `config`: 执行器配置对象

#### `async execute(instruction, plan_context=None, ...) -> ExecutionOutput`

执行自然语言指令。

**参数:**
- `instruction` (str): 自然语言指令，如 "点击游戏按钮"
- `plan_context` (dict, optional): 计划上下文
  - `overall_plan`: 整体计划
  - `current_sub_goal`: 当前子目标
- `historical_actions` (list, optional): 历史动作列表
- `execution_tips` (str, optional): 执行建议
- `key_infos` (list, optional): 关键信息列表
- `language` (str, optional): 指令语言，默认 "Chinese"

**返回:**
- `ExecutionOutput`: 执行结果对象

#### `get_session_summary() -> dict`

获取会话摘要。

**返回:**
- dict: 包含会话统计信息

### ExecutionOutput

执行结果对象。

**属性:**
- `success` (bool): 是否执行成功
- `instruction` (str): 执行的指令
- `actions_taken` (list): 执行的动作列表
- `action_thought` (str): LLM的动作思考
- `action_expectation` (str): 预期结果
- `execution_time` (float): 执行时间（秒）
- `timestamp` (str): 执行时间戳
- `output_files` (dict): 输出文件路径字典
- `screen_before` (ScreenInfo): 执行前的屏幕信息
- `screen_after` (ScreenInfo): 执行后的屏幕信息
- `error` (str, optional): 错误信息

**方法:**
- `to_dict()`: 转换为字典
- `to_json()`: 转换为JSON字符串
- `save_to_file(filepath)`: 保存到文件

## 使用场景

### 1. 独立使用

```python
from fairy_executor import ExecutorConfig, FairyExecutor

config = ExecutorConfig.from_env()
executor = FairyExecutor(config)

result = await executor.execute("点击游戏按钮")
```

### 2. 集成到LangGraph

```python
from langgraph.graph import StateGraph
from fairy_executor import FairyExecutor

class TestAgent:
    def __init__(self, executor: FairyExecutor):
        self.executor = executor

    async def execute_node(self, state):
        result = await self.executor.execute(
            instruction=state["current_instruction"],
            plan_context=state["plan_context"]
        )
        state["results"].append(result)
        return state

# 构建工作流
workflow = StateGraph(AgentState)
workflow.add_node("execute", agent.execute_node)
```

### 3. 顺序执行多个指令

```python
executor = FairyExecutor(config)
historical_actions = []

for instruction in ["点击游戏", "向下滚动", "点击第一个游戏"]:
    result = await executor.execute(
        instruction=instruction,
        historical_actions=historical_actions
    )

    if result.success:
        historical_actions.extend(result.actions_taken)
    else:
        break
```

### 4. 使用执行建议

```python
# 从RAG系统获取执行建议
tips = """
- 游戏按钮通常在底部导航栏
- 如果看不到目标元素，尝试向下滚动
"""

result = await executor.execute(
    instruction="点击游戏按钮",
    execution_tips=tips
)
```

## 输出管理

执行器会自动保存以下文件：

```
output/
└── 20231210_143022/          # 会话目录（时间戳）
    ├── screenshots/           # 截图
    │   ├── exec_001_before.jpg
    │   └── exec_001_after.jpg
    ├── marked_images/         # 标记图像（Set-of-Marks模式）
    │   ├── exec_001_before_marked.jpg
    │   └── exec_001_before_mapping.json
    ├── logs/                  # 日志
    │   └── fairy_executor.log
    └── results/               # 执行结果
        └── result_2023-12-10_14-30-22.json
```

## 日志配置

```python
from fairy_executor.logger import setup_logger
from pathlib import Path

# 基本配置
setup_logger(log_level="INFO")

# 完整配置
setup_logger(
    log_level="DEBUG",
    log_file=Path("output/logs/app.log"),
    enable_console=True,
    enable_file=True
)

# 获取logger
from fairy_executor.logger import get_logger
logger = get_logger("MyModule")
logger.info("日志消息")
```

## 与原始Fairy的区别

| 特性 | 原始Fairy | Fairy Executor |
|------|----------|----------------|
| 框架依赖 | 依赖Citlali框架 | 独立运行 |
| 配置方式 | 分散在多个文件 | 统一配置管理 |
| 日志系统 | 自定义日志 | loguru标准化 |
| 输出管理 | 手动管理 | 自动保存和组织 |
| 集成难度 | 需要理解框架 | 简单直接 |
| 模块化 | 耦合度高 | 高度模块化 |

## 架构

```
fairy_executor/
├── __init__.py          # 模块入口
├── config.py            # 配置管理
├── executor.py          # 核心执行器
├── output.py            # 输出管理
├── logger.py            # 日志管理
└── README.md            # 文档
```

## 示例代码

完整示例请查看：
- `integration/basic_usage.py` - 基本使用示例
- `integration/langgraph_integration.py` - LangGraph集成示例

## 常见问题

### Q: 为什么点击位置不准确？

A: 确保配置了视觉模型（`VISUAL_PROMPT_LMM_API_NAME`），并且 `NON_VISUAL_MODE=False` 以启用Set-of-Marks标记模式。

### Q: 如何查看详细的执行日志？

A: 设置 `LOG_LEVEL=DEBUG` 并启用文件日志：

```python
setup_logger(
    log_level="DEBUG",
    log_file=Path("output/logs/debug.log")
)
```

### Q: 如何传递给其他agent使用？

A: `ExecutionOutput` 对象包含所有必要信息：

```python
result = await executor.execute("点击游戏")

# 传递给其他agent
next_agent.process(
    screen_info=result.screen_after,
    actions_taken=result.actions_taken,
    output_files=result.output_files
)
```

### Q: 支持哪些动作类型？

A: 支持以下原子动作：
- `Tap`: 点击
- `LongPress`: 长按
- `Swipe`: 滑动
- `Input`: 输入文本
- `Wait`: 等待
- `Back`: 返回
- `Home`: 主页
- `Enter`: 回车

## 许可证

与Fairy项目相同。
