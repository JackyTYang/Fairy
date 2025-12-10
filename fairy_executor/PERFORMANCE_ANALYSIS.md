# Fairy Executor 性能分析

## 执行流程和耗时分析

### 完整执行流程

```
execute()
├── 1. _get_screen_info() [5-15秒]
│   ├── get_current_activity() [0.1-0.5秒]
│   ├── get_screen() [3-8秒] ⚠️ 主要耗时
│   ├── compress_image_to_jpeg() [0.1-0.5秒]
│   ├── get_keyboard_activation_status() [0.1-0.3秒]
│   └── get_perception_infos() [1-5秒] ⚠️ 可能耗时
│       ├── 视觉模型调用 (如果启用SoM)
│       └── UI解析
│
├── 2. _decide_action() [5-30秒] ⚠️ 主要耗时
│   ├── _build_action_decision_prompt() [0.01-0.1秒]
│   ├── 准备图像 [0.01-0.1秒]
│   └── model_client.create() [5-30秒] ⚠️⚠️⚠️ 最主要耗时
│       ├── 网络延迟
│       ├── API排队时间
│       └── LLM推理时间
│
├── 3. _execute_actions() [0.5-2秒]
│   └── controller.execute_actions()
│
└── 4. _get_screen_info() (again) [5-15秒]
```

**总耗时：15-60秒/次**

## 主要性能瓶颈

### 1. LLM API调用 (最主要) ⚠️⚠️⚠️

**耗时：5-30秒**

**原因：**
- 网络延迟（特别是国内访问国外API）
- API服务器排队时间
- LLM推理时间（视觉模型更慢）
- 图像上传时间（如果使用Set-of-Marks模式）

**可能的问题：**
```python
# 你的配置
CORE_LMM_MODEL_NAME=gpt-5  # ❌ 无效模型，可能导致超时或重试
CORE_LMM_API_BASE=https://api.zhizengzeng.com/v1  # 第三方代理，可能较慢
```

**优化建议：**

#### 方案1: 使用更快的模型
```bash
# 使用更快的模型
CORE_LMM_MODEL_NAME=gpt-4o-mini  # 比gpt-4o快2-3倍
# 或
CORE_LMM_MODEL_NAME=claude-3-5-haiku-20241022  # 更快的Claude模型
```

#### 方案2: 使用国内API
```bash
# 使用国内API服务
CORE_LMM_API_BASE=https://api.siliconflow.cn/v1  # 硅基流动
# 或
CORE_LMM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1  # 阿里云
```

#### 方案3: 禁用视觉模式（最快）
```bash
# 使用纯文本模式，不发送图像
NON_VISUAL_MODE=True
```

**性能对比：**
| 模式 | LLM耗时 | 准确性 |
|------|---------|--------|
| 视觉模式 (SoM) | 10-30秒 | 最高 |
| 视觉模式 (无SoM) | 8-20秒 | 高 |
| 纯文本模式 | 5-10秒 | 中等 |

### 2. 屏幕感知解析 ⚠️

**耗时：1-5秒**

**原因：**
- 调用视觉模型生成Set-of-Marks标记
- UI层次结构解析
- 图像处理

**优化建议：**

#### 方案1: 禁用Set-of-Marks
```bash
# 不使用视觉标记，直接使用坐标
NON_VISUAL_MODE=True
```

#### 方案2: 使用更快的视觉模型
```bash
# 使用更快的视觉模型
VISUAL_PROMPT_LMM_API_NAME=qwen-vl-max  # 更快的千问视觉模型
```

### 3. 截图获取 ⚠️

**耗时：3-8秒**

**原因：**
- ADB通信延迟
- 设备响应时间
- 文件传输时间

**优化建议：**

#### 方案1: 使用USB连接而非WiFi
```bash
# USB连接比WiFi快3-5倍
adb usb
```

#### 方案2: 降低截图质量
```python
# 在config中添加
screenshot_quality = 50  # 降低质量，减少传输时间
```

## 性能优化配置示例

### 配置1: 平衡模式（推荐）

```bash
# .env
DEVICE_ID=emulator-5554

# 使用快速模型
CORE_LMM_MODEL_NAME=gpt-4o-mini
CORE_LMM_API_BASE=https://api.openai.com/v1
CORE_LMM_API_KEY=sk-...

# 使用国内视觉模型
VISUAL_PROMPT_LMM_API_NAME=qwen-vl-max
VISUAL_PROMPT_LMM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
VISUAL_PROMPT_LMM_API_KEY=sk-...

# 启用Set-of-Marks（准确性优先）
NON_VISUAL_MODE=False
```

**预期性能：15-25秒/次**

### 配置2: 速度优先模式

```bash
# .env
DEVICE_ID=emulator-5554

# 使用最快的模型
CORE_LMM_MODEL_NAME=gpt-4o-mini
CORE_LMM_API_BASE=https://api.siliconflow.cn/v1  # 国内API
CORE_LMM_API_KEY=sk-...

# 禁用视觉模式
NON_VISUAL_MODE=True

# 不需要视觉模型配置
```

**预期性能：8-15秒/次**

### 配置3: 准确性优先模式

```bash
# .env
DEVICE_ID=emulator-5554

# 使用最强模型
CORE_LMM_MODEL_NAME=gpt-4o
CORE_LMM_API_BASE=https://api.openai.com/v1
CORE_LMM_API_KEY=sk-...

# 使用最好的视觉模型
VISUAL_PROMPT_LMM_API_NAME=qwen-vl-plus
VISUAL_PROMPT_LMM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
VISUAL_PROMPT_LMM_API_KEY=sk-...

# 启用Set-of-Marks
NON_VISUAL_MODE=False
```

**预期性能：20-40秒/次**

## 诊断慢速问题

### 步骤1: 启用详细日志

```python
from fairy_executor.logger import setup_logger

setup_logger(log_level="DEBUG")  # 启用DEBUG日志
```

### 步骤2: 运行测试并查看日志

```bash
python integration/basic_usage.py
```

查看日志输出：
```
17:12:52 | INFO  | 开始屏幕感知解析...
17:12:55 | INFO  | 屏幕感知解析完成，耗时: 3.2秒  # ← 屏幕感知耗时
17:12:55 | INFO  | LLM决策中...
17:12:55 | INFO  | 开始调用LLM API...
17:13:15 | INFO  | LLM API调用完成，耗时: 20.1秒  # ← LLM API耗时 ⚠️
```

### 步骤3: 分析瓶颈

根据日志判断：

**如果 "屏幕感知解析" 耗时 > 5秒：**
- 视觉模型太慢
- 建议：使用更快的视觉模型或禁用SoM

**如果 "LLM API调用" 耗时 > 15秒：**
- API太慢或网络问题
- 建议：使用更快的模型或国内API

**如果 "获取截图和UI层次" 耗时 > 5秒：**
- ADB连接慢
- 建议：使用USB连接或检查设备性能

## 你当前的问题分析

根据你的日志：
```
17:12:52 | INFO | LLM决策中...
```

卡在这里很久，说明是 **LLM API调用慢**。

**可能原因：**

1. **模型名称错误** ⚠️⚠️⚠️
   ```bash
   CORE_LMM_MODEL_NAME=gpt-5  # ❌ 这个模型不存在！
   ```
   - API可能在重试或超时
   - 建议改为：`gpt-4o-2024-11-20` 或 `gpt-4o-mini`

2. **API代理慢**
   ```bash
   CORE_LMM_API_BASE=https://api.zhizengzeng.com/v1
   ```
   - 第三方代理可能较慢
   - 建议使用官方API或更快的代理

3. **网络问题**
   - 国内访问国外API可能很慢
   - 建议使用国内API服务

## 立即优化建议

### 1. 修复模型名称（必须）

```bash
# .env
CORE_LMM_MODEL_NAME=gpt-4o-mini  # ✅ 改为有效的模型
```

### 2. 测试API速度

```python
import time
import asyncio
from Citlali.models.openai.client import OpenAIChatClient
from Citlali.models.entity import ChatMessage

async def test_api_speed():
    client = OpenAIChatClient({
        "model": "gpt-4o-mini",
        "api_key": "sk-...",
        "base_url": "https://api.zhizengzeng.com/v1"
    })

    t0 = time.time()
    response = await client.create([
        ChatMessage(content="Hello", type="UserMessage")
    ])
    print(f"API响应时间: {time.time() - t0:.2f}秒")

asyncio.run(test_api_speed())
```

### 3. 如果API太慢，切换到国内服务

```bash
# 使用硅基流动（国内，支持OpenAI格式）
CORE_LMM_API_BASE=https://api.siliconflow.cn/v1
CORE_LMM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct

# 或使用阿里云
CORE_LMM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
CORE_LMM_MODEL_NAME=qwen-turbo
```

## 性能监控

我已经在代码中添加了详细的性能日志，现在运行时会显示：

```
17:12:50 | DEBUG | 获取Activity耗时: 0.15秒
17:12:52 | DEBUG | 获取截图和UI层次耗时: 2.31秒
17:12:52 | DEBUG | 压缩图像耗时: 0.08秒
17:12:52 | DEBUG | 获取键盘状态耗时: 0.12秒
17:12:52 | INFO  | 开始屏幕感知解析...
17:12:55 | INFO  | 屏幕感知解析完成，耗时: 3.2秒
17:12:55 | INFO  | LLM决策中...
17:12:55 | DEBUG | Prompt构建耗时: 0.02秒, 长度: 2345字符
17:12:55 | DEBUG | 图像准备耗时: 0.01秒, 图像数: 1
17:12:55 | INFO  | 开始调用LLM API...
17:13:15 | INFO  | LLM API调用完成，耗时: 20.1秒  # ← 主要瓶颈
17:13:15 | DEBUG | 响应解析耗时: 0.05秒
```

这样你就能清楚地看到每个步骤的耗时，快速定位性能瓶颈！

## 总结

**当前问题：** LLM API调用慢（可能是模型名称错误导致）

**立即修复：**
1. 修改 `.env` 中的 `CORE_LMM_MODEL_NAME=gpt-4o-mini`
2. 运行测试，查看详细的性能日志
3. 根据日志分析具体瓶颈

**长期优化：**
1. 使用更快的模型（gpt-4o-mini, claude-haiku）
2. 使用国内API服务
3. 考虑禁用视觉模式（如果准确性要求不高）
