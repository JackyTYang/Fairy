# 迁移指南：从 minimal_executor 到 fairy_executor

本指南帮助你从旧的 `minimal_executor.py` 迁移到新的模块化 `fairy_executor` 包。

## 主要变化

### 1. 模块结构

**之前:**
```
minimal_executor.py  (单文件，~735行)
```

**现在:**
```
fairy_executor/
├── __init__.py      # 模块入口
├── config.py        # 配置管理
├── executor.py      # 核心执行器
├── output.py        # 输出管理
├── logger.py        # 日志管理
└── README.md        # 文档
```

### 2. 类名变化

| 旧名称 | 新名称 | 说明 |
|--------|--------|------|
| `MinimalFairyExecutor` | `FairyExecutor` | 主执行器类 |
| `MinimalExecutorConfig` | `ExecutorConfig` | 配置类 |
| `ExecutionResult` | `ExecutionOutput` | 执行结果类 |

### 3. 导入方式

**之前:**

```python
from integration.deprecated.minimal_executor import MinimalFairyExecutor, MinimalExecutorConfig, ExecutionResult
```

**现在:**
```python
from fairy_executor import FairyExecutor, ExecutorConfig, ExecutionOutput
```

## 迁移步骤

### 步骤1: 更新导入语句

**之前:**

```python
from integration.deprecated.minimal_executor import (
    MinimalFairyExecutor,
    MinimalExecutorConfig,
    ExecutionResult
)
```

**现在:**
```python
from fairy_executor import (
    FairyExecutor,
    ExecutorConfig,
    ExecutionOutput
)
from fairy_executor.logger import setup_logger
```

### 步骤2: 更新配置方式

**之前:**
```python
from Fairy.config.model_config import ModelConfig

visual_model_config = ModelConfig(
    model_name=os.getenv("VISUAL_PROMPT_LMM_API_NAME"),
    model_temperature=0,
    model_info={"vision": True, "function_calling": False, "json_output": False},
    api_base=os.getenv("VISUAL_PROMPT_LMM_API_BASE"),
    api_key=os.getenv("VISUAL_PROMPT_LMM_API_KEY")
)

config = MinimalExecutorConfig(
    device=os.getenv("DEVICE_ID"),
    model_client=core_model_client,
    visual_prompt_model_config=visual_model_config,
    text_summarization_model_config=text_summary_config,
    non_visual_mode=False
)

executor = MinimalFairyExecutor(
    device=config.device,
    model_client=config.model_client,
    config=config
)
```

**现在:**
```python
# 方式1: 从环境变量自动加载（推荐）
config = ExecutorConfig.from_env()
executor = FairyExecutor(config)

# 方式2: 手动配置
from fairy_executor import ModelConfig, DeviceConfig, PerceptionConfig, OutputConfig

config = ExecutorConfig(
    device=DeviceConfig(device_id=os.getenv("DEVICE_ID")),
    core_model=ModelConfig.from_env("CORE_LMM"),
    perception=PerceptionConfig.from_env(),
    output=OutputConfig(output_dir="output")
)
executor = FairyExecutor(config)
```

### 步骤3: 更新执行方法调用

**之前:**
```python
result = await executor.execute_instruction(
    instruction="点击游戏按钮",
    plan_context={
        "overall_plan": "进入游戏页面",
        "current_sub_goal": "点击游戏按钮"
    }
)
```

**现在:**
```python
result = await executor.execute(  # 方法名从 execute_instruction 改为 execute
    instruction="点击游戏按钮",
    plan_context={
        "overall_plan": "进入游戏页面",
        "current_sub_goal": "点击游戏按钮"
    }
)
```

### 步骤4: 更新日志配置

**之前:**
```python
# 使用print语句
print(f"🚀 [DEBUG] 开始执行指令: {instruction}")
```

**现在:**
```python
# 使用loguru
from fairy_executor.logger import setup_logger, get_logger

setup_logger(log_level="INFO")
logger = get_logger("MyApp")
logger.info(f"开始执行指令: {instruction}")
```

### 步骤5: 更新结果处理

**之前:**
```python
result: ExecutionResult

print(f"成功: {result.success}")
print(f"动作: {result.actions_taken}")
print(f"思考: {result.action_thought}")
```

**现在:**
```python
result: ExecutionOutput

print(f"成功: {result.success}")
print(f"动作: {result.actions_taken}")
print(f"思考: {result.action_thought}")

# 新增：输出文件管理
print(f"输出文件: {result.output_files}")
print(f"截图: {result.output_files['screenshot_before']}")
print(f"结果JSON: {result.output_files['result']}")

# 新增：保存到文件
result.save_to_file(Path("my_result.json"))
```

## 完整示例对比

### 旧代码 (minimal_executor.py)

```python
import asyncio
import os
from dotenv import load_dotenv
from integration.deprecated.minimal_executor import MinimalFairyExecutor, MinimalExecutorConfig
from Citlali.models.openai.client import OpenAIChatClient
from Fairy.config.model_config import ModelConfig


async def main():
    load_dotenv()

    # 创建模型客户端
    core_model_client = OpenAIChatClient({
        "model": os.getenv("CORE_LMM_MODEL_NAME"),
        "api_key": os.getenv("CORE_LMM_API_KEY"),
        "base_url": os.getenv("CORE_LMM_API_BASE")
    })

    # 配置视觉模型
    visual_model_config = ModelConfig(
        model_name=os.getenv("VISUAL_PROMPT_LMM_API_NAME"),
        model_temperature=0,
        model_info={"vision": True, "function_calling": False, "json_output": False},
        api_base=os.getenv("VISUAL_PROMPT_LMM_API_BASE"),
        api_key=os.getenv("VISUAL_PROMPT_LMM_API_KEY")
    )

    text_summary_config = ModelConfig(
        model_name=os.getenv("RAG_LLM_API_NAME"),
        model_temperature=0,
        model_info={"vision": False, "function_calling": False, "json_output": False},
        api_base=os.getenv("RAG_LLM_API_BASE"),
        api_key=os.getenv("RAG_LLM_API_KEY")
    )

    # 创建配置
    config = MinimalExecutorConfig(
        device=os.getenv("DEVICE_ID"),
        model_client=core_model_client,
        visual_prompt_model_config=visual_model_config,
        text_summarization_model_config=text_summary_config,
        non_visual_mode=False
    )

    # 创建执行器
    executor = MinimalFairyExecutor(
        device=config.device,
        model_client=config.model_client,
        config=config
    )

    # 执行指令
    result = await executor.execute_instruction(
        instruction="点击游戏按钮",
        plan_context={
            "overall_plan": "进入游戏页面",
            "current_sub_goal": "点击游戏按钮"
        }
    )

    print(f"执行成功: {result.success}")
    print(f"执行的动作: {result.actions_taken}")


asyncio.run(main())
```

### 新代码 (fairy_executor)

```python
import asyncio
from fairy_executor import ExecutorConfig, FairyExecutor
from fairy_executor.logger import setup_logger

async def main():
    # 配置日志
    setup_logger(log_level="INFO")

    # 从环境变量加载配置（自动处理所有模型配置）
    config = ExecutorConfig.from_env()

    # 创建执行器
    executor = FairyExecutor(config)

    # 执行指令
    result = await executor.execute(
        instruction="点击游戏按钮",
        plan_context={
            "overall_plan": "进入游戏页面",
            "current_sub_goal": "点击游戏按钮"
        }
    )

    # 查看结果
    print(f"执行成功: {result.success}")
    print(f"执行的动作: {result.actions_taken}")
    print(f"输出文件: {result.output_files}")

    # 获取会话摘要
    summary = executor.get_session_summary()
    print(f"会话摘要: {summary}")

asyncio.run(main())
```

## 新功能

### 1. 自动输出管理

新版本会自动保存所有输出文件：

```python
result = await executor.execute("点击游戏")

# 自动保存的文件
print(result.output_files)
# {
#     'screenshot_before': 'output/.../screenshots/exec_001_before.jpg',
#     'screenshot_after': 'output/.../screenshots/exec_001_after.jpg',
#     'marked_image_before': 'output/.../marked_images/exec_001_before_marked.jpg',
#     'mark_mapping_before': 'output/.../marked_images/exec_001_before_mapping.json',
#     'result': 'output/.../results/result_2023-12-10_14-30-22.json'
# }
```

### 2. 标准化日志

使用loguru提供美观的日志输出：

```python
from fairy_executor.logger import setup_logger

setup_logger(
    log_level="DEBUG",
    log_file=Path("logs/app.log"),
    enable_console=True,
    enable_file=True
)
```

### 3. 会话管理

获取会话统计信息：

```python
summary = executor.get_session_summary()
# {
#     'session_id': '20231210_143022',
#     'session_dir': 'output/20231210_143022',
#     'execution_count': 5,
#     'screenshots_count': 10,
#     'marked_images_count': 10,
#     'results_count': 5
# }
```

### 4. 结果序列化

轻松保存和传递结果：

```python
result = await executor.execute("点击游戏")

# 转换为字典
result_dict = result.to_dict()

# 转换为JSON
result_json = result.to_json()

# 保存到文件
result.save_to_file(Path("result.json"))
```

## 配置文件变化

### .env 文件

新版本的 `.env` 文件配置更简洁：

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

# 输出配置（新增）
OUTPUT_DIR=output
LOG_LEVEL=INFO
NON_VISUAL_MODE=False
```

## 常见问题

### Q: 旧代码还能用吗？

A: 可以，`minimal_executor.py` 仍然可用，但建议迁移到新版本以获得更好的功能和维护。

### Q: 迁移需要多长时间？

A: 对于简单的使用场景，通常只需要5-10分钟更新导入和配置代码。

### Q: 新版本性能如何？

A: 新版本在性能上与旧版本相当，但提供了更好的日志和输出管理，便于调试和分析。

### Q: 如何逐步迁移？

A: 建议的迁移策略：
1. 先在测试环境中使用新版本
2. 验证功能正常后，逐步迁移生产代码
3. 保留旧代码作为备份，直到完全验证新版本

### Q: 遇到问题怎么办？

A:
1. 查看 [fairy_executor/README.md](fairy_executor/README.md)
2. 查看 [integration/](integration/) 目录中的示例
3. 检查日志文件（设置 `LOG_LEVEL=DEBUG`）
4. 提交Issue到项目仓库

## 兼容性说明

### 保持兼容的部分

- 执行逻辑完全相同
- 支持相同的动作类型
- 使用相同的底层工具（UiAutomator、ScreenPerceptor等）
- 环境变量名称保持一致

### 不兼容的部分

- 类名变化（`MinimalFairyExecutor` → `FairyExecutor`）
- 方法名变化（`execute_instruction` → `execute`）
- 配置方式变化（更简洁的配置接口）
- 日志输出格式变化（使用loguru）

## 总结

新版本 `fairy_executor` 提供了：

✅ 更清晰的模块结构
✅ 更简洁的配置方式
✅ 标准化的日志系统
✅ 自动化的输出管理
✅ 更好的文档和示例
✅ 更容易集成到其他框架

建议尽快迁移到新版本以获得更好的开发体验！
