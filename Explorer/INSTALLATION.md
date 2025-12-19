# Explorer 安装和配置指南

## 📋 前置要求

1. **Python环境**
   ```bash
   python >= 3.11
   conda environment: fairy_v1
   ```

2. **已安装的依赖**
   - Executor 模块已配置（需要 Executor/.env）
   - Perceptor 相关工具
   - ADB 工具链

3. **Android设备**
   - USB调试已启用
   - 通过ADB连接

## 🚀 快速开始

### 步骤 1: 配置环境变量

```bash
cd /path/to/Fairy/Explorer
cp .env.example .env
```

编辑 `.env` 文件，填入实际配置：

```bash
# LLM配置（用于计划生成）
EXPLORER_LLM_MODEL_NAME=gpt-4o-2024-11-20
EXPLORER_LLM_API_KEY=sk-your-api-key
EXPLORER_LLM_API_BASE=https://api.openai.com/v1
EXPLORER_LLM_TEMPERATURE=0

# 视觉模型配置（用于屏幕感知）
EXPLORER_VISUAL_MODEL_NAME=qwen-vl-plus
EXPLORER_VISUAL_API_KEY=sk-your-api-key
EXPLORER_VISUAL_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1

# ADB配置
EXPLORER_ADB_PATH=/path/to/adb
EXPLORER_DEVICE_ID=  # 可选，留空则自动检测

# 输出配置
EXPLORER_OUTPUT_DIR=output/exploration

# 执行配置
EXPLORER_MAX_EXPLORATION_STEPS=50
EXPLORER_REPLAN_ON_EVERY_STEP=true
EXPLORER_REPLAN_INTERVAL=1
EXPLORER_MAX_PLAN_STEPS=20
```

### 步骤 2: 验证安装

```bash
# 测试模块导入
python3 -c "from Explorer import ExplorerConfig, FairyExplorer; print('✅ 导入成功')"

# 测试配置加载（需要先配置.env）
python3 -c "from Explorer import ExplorerConfig; config = ExplorerConfig.from_env(); print(config)"
```

### 步骤 3: 连接设备

```bash
# 检查设备连接
adb devices

# 应该看到类似输出:
# List of devices attached
# XXXXXXXXXX    device
```

### 步骤 4: 运行示例

```bash
cd /path/to/Fairy
python integration/explorer_example.py
```

## 📁 目录结构

完成后，您的目录应该是：

```
Fairy/
├── Explorer/
│   ├── __init__.py
│   ├── config.py
│   ├── entities.py
│   ├── explorer.py
│   ├── planner.py
│   ├── perception_wrapper.py
│   ├── state_tracker.py
│   ├── logger.py
│   ├── .env                    # ← 需要配置
│   ├── .env.example
│   ├── README.md
│   ├── DESIGN.md
│   └── INSTALLATION.md
├── Executor/
│   ├── .env                    # ← 需要配置
│   └── ...
├── Perceptor/
│   └── ...
└── integration/
    └── explorer_example.py
```

## ⚙️ 配置说明

### 必需配置

以下配置项**必须填写**：

1. **EXPLORER_LLM_MODEL_NAME**: LLM模型名称
2. **EXPLORER_LLM_API_KEY**: LLM API密钥
3. **EXPLORER_LLM_API_BASE**: LLM API地址
4. **EXPLORER_VISUAL_MODEL_NAME**: 视觉模型名称
5. **EXPLORER_VISUAL_API_KEY**: 视觉模型API密钥
6. **EXPLORER_VISUAL_API_BASE**: 视觉模型API地址
7. **EXPLORER_ADB_PATH**: ADB可执行文件路径

### 可选配置

以下配置项有默认值，可按需修改：

- **EXPLORER_LLM_TEMPERATURE**: LLM温度（默认0）
- **EXPLORER_DEVICE_ID**: 设备ID（默认自动检测）
- **EXPLORER_OUTPUT_DIR**: 输出目录（默认output/exploration）
- **EXPLORER_MAX_EXPLORATION_STEPS**: 最大探索步骤（默认50）
- **EXPLORER_REPLAN_ON_EVERY_STEP**: 是否每步都重新规划（默认true）
- **EXPLORER_REPLAN_INTERVAL**: 重新规划间隔（默认1）
- **EXPLORER_MAX_PLAN_STEPS**: 单次计划最大步骤（默认20）

## 🐛 常见问题

### 1. 配置文件找不到

**错误**：
```
ValueError: 缺少必需的环境变量
```

**解决**：
- 确保 `Explorer/.env` 文件存在
- 检查文件权限
- 确保所有必需的配置项都已填写

### 2. ADB设备未找到

**错误**：
```
ADB device not found
```

**解决**：
```bash
# 检查ADB路径是否正确
which adb

# 检查设备连接
adb devices

# 重启ADB服务
adb kill-server
adb start-server
```

### 3. API调用失败

**错误**：
```
API call failed / Authentication error
```

**解决**：
- 检查API密钥是否正确
- 检查API地址是否可访问
- 确认账户有足够的配额

### 4. 导入错误

**错误**：
```
ModuleNotFoundError: No module named 'Explorer'
```

**解决**：
```bash
# 确保在正确的目录
cd /path/to/Fairy

# 确保激活了正确的conda环境
conda activate fairy_v1

# 检查Python路径
python3 -c "import sys; print(sys.path)"
```

## 🧪 测试

### 快速测试

```python
import asyncio
from Explorer import ExplorerConfig, FairyExplorer, ExplorationTarget, setup_logger

async def test():
    setup_logger(log_level="INFO")
    config = ExplorerConfig.from_env()
    print(f"✅ 配置加载成功")
    print(config)

asyncio.run(test())
```

### 完整测试

参考 `integration/explorer_example.py`

## 📚 下一步

配置完成后，您可以：

1. 阅读 [README.md](README.md) 了解详细用法
2. 查看 [DESIGN.md](DESIGN.md) 了解架构设计
3. 运行 `integration/explorer_example.py` 进行测试
4. 根据需要自定义探索目标

## 🆘 获取帮助

如果遇到问题，可以：

1. 检查日志文件（`output/exploration/*/explorer.log`）
2. 查看详细的错误堆栈
3. 参考文档和示例代码
4. 检查配置是否正确
