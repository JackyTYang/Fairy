# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fairy is an interactive, multi-agent mobile assistant powered by Large Multi-modal Models (LMMs). It enables autonomous task execution on Android devices through ADB, supporting cross-app collaboration, interactive execution, and continuous learning with RAG-based knowledge accumulation.

## Running the Project

### Setup
```bash
# Create environment
conda create -n fairy_v1 python=3.11
conda activate fairy_v1
pip install -r requirements.txt
```

### Running Tasks
```bash
# Via command line
python fairy_starter.py --task "Order me a McDonald's burger."

# Or modify fairy_starter.py directly and run
python fairy_starter.py
```

## Architecture

### Core Framework: Citlali

Citlali is the underlying runtime framework that Fairy is built on. It provides:

- **Runtime (`CitlaliRuntime`)**: Singleton runtime managing workers and message passing
- **Worker**: Base class for all system components. Workers listen to messages via decorated methods (`@listener`)
- **Agent**: Extends Worker, adds LLM integration with system messages and response parsing
- **Message System**: Pub/sub architecture with two listener types:
  - `ON_CALLED`: Direct RPC-style calls to specific workers
  - `ON_NOTIFIED`: Channel-based broadcasts to subscribed workers
- **Model Clients**: OpenAI-compatible chat client in `Citlali/models/openai/`

### Fairy Application Layer

Built on Citlali, Fairy implements the mobile assistant through:

**Agent Hierarchy:**
- **Global Planners** (`global_planner_agents/`): Break down user instructions into app-level sub-goals
  - `GlobalPlannerAgent`: Creates initial high-level plan
  - `GlobalRePlannerAgent`: Adjusts plan based on execution feedback

- **App Executors** (`app_executor_agents/`): Execute tasks within a single app
  - `AppPlannerAgent`: Plans action sequences for current sub-goal
  - `AppReflectorAgent`: Reflects on execution results and decides next steps
  - `AppRePlannerForActExecAgent`: Replans after action execution
  - `AppRePlannerForUsrChatAgent`: Replans after user chat interaction
  - `AppActionDeciderAgent`: Decides specific actions from parsed screen info
  - `KeyInfoExtractorAgent`: Extracts key information from screens
  - `UserInteractorAgent`: Handles user interaction when needed

**Tools** (`tools/`):
- `ScreenPerceptor`: Captures and parses screen content (supports FVP and SSIP modes)
- `ActionExecutor`: Executes actions on device (via UI Automator or ADB)
- `AppInfoManager`: Manages app metadata collection
- `UserDialoger`: Handles user dialog interactions
- `TaskManager`: Manages task lifecycle

**Memory** (`memory/`):
- `ShortTimeMemoryManager`: Manages conversation and execution context
- `LongTimeMemoryManager`: RAG-based knowledge retrieval from `data/` directory
  - `execution_tips.txt`: Tips for action execution
  - `execution_error_tips.txt`: Error handling guidance
  - `plan_tips.txt`: Planning strategies

### Configuration

Configuration is centralized in `Fairy/config/`:
- `fairy_config.py`: Main config class with `FairyEnvConfig` loading from `.env`
- `model_config.py`: Model client configurations

## Critical Environment Variables

The `.env` file MUST be properly configured before running:

```dotenv
# Core LMM for agent reasoning (REQUIRED - must be actual model name)
CORE_LMM_MODEL_NAME=gpt-4o-2024-11-20  # NOT <YOUR_LMM_MODEL_NAME>
CORE_LMM_API_BASE=https://api.openai.com/v1
CORE_LMM_API_KEY=sk-...

# RAG components (REQUIRED)
RAG_LLM_API_NAME=qwen-turbo-0428
RAG_LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
RAG_LLM_API_KEY=sk-...

# Embedding model
HF_ENDPOINT=https://hf-mirror.com
RAG_EMBED_MODEL_NAME=intfloat/multilingual-e5-large-instruct

# Visual understanding (REQUIRED)
VISUAL_PROMPT_LMM_API_NAME=qwen-vl-plus
VISUAL_PROMPT_LMM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
VISUAL_PROMPT_LMM_API_KEY=sk-...

# ADB configuration (REQUIRED)
ADB_PATH=/path/to/adb

# Execution modes
ACTION_EXECUTOR_TYPE=UI_AUTOMATOR  # or ADB
SCREENSHOT_GETTER_TYPE=UI_AUTOMATOR
SCREEN_PERCEPTION_TYPE=SSIP  # or FVP
INTERACTION_MODE=DIALOG  # or CONSOLE
NON_VISUAL_MODE=False
MANUAL_COLLECT_APP_INFO=True
REFLECTION_POLICY=standalone  # or hybrid
```

**Common Error**: If `CORE_LMM_MODEL_NAME` is left as `<YOUR_LMM_MODEL_NAME>`, API calls return `None` causing `TypeError: object of type 'NoneType' has no len()` in `Citlali/models/openai/client.py:155`.

## Execution Flow

1. **Initialization** (`fairy.py:start()`):
   - Validates ADB device connection
   - Creates task temp directory structure (`tmp/TaskName_timestamp/`)
   - Configures logging to both stdout and files
   - Registers all agents, tools, and memory managers with runtime
   - Publishes INIT event to GLOBAL_CHANNEL

2. **Global Planning**:
   - `GlobalPlannerAgent` receives INIT event
   - Creates high-level plan of app-level sub-goals
   - Publishes to APP_CHANNEL for execution

3. **App Execution Loop**:
   - For each sub-goal, `AppPlannerAgent` creates action plan
   - `ScreenPerceptor` captures and parses current screen
   - `AppActionDeciderAgent` decides action based on screen + plan + memory
   - `ActionExecutor` executes action on device
   - `AppReflectorAgent` evaluates result, decides to continue/replan/escalate
   - Loop continues until sub-goal complete or needs global replan

4. **Memory Integration**:
   - Long-term: RAG retrieval from `data/*.txt` files with app-specific filtering
   - Short-term: Conversation history and execution context

5. **Recovery**: `FairyRecovery` maintains restore points for error recovery

## Key Design Patterns

### Worker Registration
All components are registered as lambdas to defer instantiation until runtime starts:
```python
runtime.register(lambda: GlobalPlannerAgent(runtime, self._config))
```

### Message Flow
- Direct calls: `await self.call(worker_name, message)`
- Broadcasts: `await self.publish(channel, message)`
- Listeners use decorators with optional filters

### Agent-LLM Integration
Agents inherit from `Agent` base class which provides:
- `request_llm()`: Send messages to LLM with system messages
- `parse_response()`: Override to parse LLM responses
- Automatic logging of requests/responses to `agent_res&req_log.log`

### Screen Perception
Two modes:
- **SSIP**: Structured screen information parsing (default)
- **FVP**: Full visual perception

### Action Execution
Two modes:
- **UI_AUTOMATOR**: Uses UI Automator for precise element interaction (default)
- **ADB**: Direct ADB commands (fallback)

## Data Files

The RAG system requires files in `Fairy/data/`:
- These must be `.txt` files (NOT directories)
- Loaded via `SimpleDirectoryReader(input_files=[str(path)])` pattern
- Metadata includes `app_package_name` for app-specific filtering
- Common tips should be in files named `common.txt`

## Logging

Logs are written to `tmp/TaskName_timestamp/log/`:
- `fairy_sys_log.log`: Main Fairy system events (DEBUG level)
- `citlali_sys_log.log`: Citlali framework events
- `agent_res&req_log.log`: All LLM requests and responses
- `screen_perception_log.log`: Screen parsing details

All logs also output to stdout with color coding.

## Android Device Requirements

- Android device (iOS not supported)
- Developer mode enabled
- USB debugging enabled
- USB installation enabled (for UI Automator mode)
- Connected via USB or emulator
- ADB accessible from command line

## Common Issues

1. **Missing model name**: Ensure `CORE_LMM_MODEL_NAME` is set to actual model, not placeholder
2. **ADB not found**: Verify `ADB_PATH` points to actual `adb` binary
3. **No device**: Check `adb devices` output before running
4. **RAG initialization**: Data files must exist as `.txt` files, not directories
5. **API failures**: Check API keys and base URLs are correct for your provider
