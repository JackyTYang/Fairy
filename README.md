
<div style="display: flex; justify-content: center; align-items: center; flex-direction: column; margin: 20px 0px">
  <img src="README/images/logo.png" alt="logo" width="200">
  <h1 style="margin: 10px; padding: 0px; text-align: center">Fairy V2: A Multi-agent Mobile Assistant as Fast as RPA via Adaptive Task Template</h1>
  <p style="text-align: center">Anonymous authors</p>
  <img src="README/images/case.png" alt="logo" width="90%"/>
</div>



Welcome to the Fairy project! Fairy is an interactive, multi-agent mobile assistant that can continuously evolve and accumulate app knowledge during task execution. Built on the foundation of large multi-modal models (LMMs), Fairy offers a breakthrough in mobile agent technology by enabling cross-app collaboration, interactive execution, and continuous learning to enhance the user experience.

## 📦Installation

### Python Environment

To get started with Fairy, clone the repository and install the necessary dependencies:

```bash
conda create -n fairy_v1 python=3.11
conda activate fairy_v1
pip install -r requirements.txt
```

### ADB & Android Environment
Fairy requires ADB (Android Debug Bridge) to interact with mobile devices. Ensure you have ADB installed and configured on your system. You can download it from the [Android SDK Platform Tools](https://developer.android.com/studio/releases/platform-tools).

Fairy does not support **iOS** at this time. You must have an **Android** device connected to your computer via USB or use the **Android Emulator**. Make sure your Android device is in `Developer Mode` and has `USB Debugging` enabled. If you're using `UI Automator` in Fairy (which is used by default), you also need to enable `USB Installation` in `Developer Options`.

### Fairy Config

Please locate the `.env` file and complete the following configuration:

1. Set the backbone model for the Agent reasoning. You should replace `<YOUR_LMM_MODEL_NAME>`, `<YOUR_LMM_API_BASE>` `<YOUR_LMM_API_KEY>` with your model, base URL, and API key.
```
CORE_LMM_MODEL_NAME=<YOUR_LMM_MODEL_NAME> # e.g., gpt-4o-2024-11-20
CORE_LMM_API_BASE=<YOUR_LMM_API_BASE> # e.g., https://api.openai.com/v1
CORE_LMM_API_KEY=<YOUR_LMM_API_KEY> # e.g., sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
2. Set the RAG model and embedding model for knowledge retrieval and processing. We default to `intfloat/multilingual-e5-large-instruct` for embedding and use `qwen-turbo-0428` for retrieval. You should replace `<YOUR_RAG_LLM_API_KEY>` with your API key. Please follow this to get the [Qwen API Key](https://help.aliyun.com/zh/model-studio/get-api-key).
```
# We recommend not modifying the default model.

RAG_LLM_API_NAME=qwen-turbo-0428
RAG_LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
RAG_LLM_API_KEY=<YOUR_RAG_LLM_API_KEY> # e.g., sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

HF_ENDPOINT=<HUGGING_FACE_ENDPOINT> # e.g., https://huggingface.co
RAG_EMBED_MODEL_NAME=intfloat/multilingual-e5-large-instruct
```

3. Set the visual prompt model for image understanding in mobile screenshots. We default to `qwen-vl-plus` for visual tasks. You should replace `<YOUR_VISUAL_PROMPT_LMM_API_KEY>` with your API key. Please follow this to get the [Qwen API Key](https://help.aliyun.com/zh/model-studio/get-api-key).
```
VISUAL_PROMPT_LMM_API_NAME=qwen-vl-plus
VISUAL_PROMPT_LMM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
VISUAL_PROMPT_LMM_API_KEY=<YOUR_VISUAL_PROMPT_LMM_API_KEY> # e.g., sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

4. Set the ADB path to your local ADB installation. Ensure that the path is correct and points to the `adb.exe` file. You can find it in your Android SDK installation directory, typically under `platform-tools`.
```
ADB_PATH=<YOUR_ADB_PATH> # e.g., C:/Users/<YOUR_USER_NAME>/AppData/Local/Android/Sdk/platform-tools/adb.exe
```

## 📲 Start

To use Fairy, run the main program and provide a task description. Fairy will automatically control the relevant apps, execute the required actions:

```bash
python fairy_starter.py --task "Order me a McDonald's burger."
```

## 📖 Research Homepage

For more details on Fairy's design, case studies, evaluation tasks, and the full source code, please visit the project [Homepage](https://neosunjz.github.io/FairyResearch).

## License

Fairy is licensed under the Apache License 2.0 License. See the LICENSE file for more details. 

The copyright of the **project logo** belongs to miHoYo & HoYoverse. It is used for **non-commercial** purposes (derivative work). This project is **NOT** affiliated with miHoYo & HoYoverse or its affiliates.