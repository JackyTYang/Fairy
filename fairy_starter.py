import asyncio
import os

from Fairy.config.model_config import CoreChatModelConfig, RAGChatModelConfig, RAGEmbedModelConfig
from Fairy.fairy import FairyCore
from Fairy.config.fairy_config import FairyConfig

# 请其他同学使用自己的OPENAI_API_KEY来请求
# 以下是Jiazheng.Sun的API Key, 请勿使用
os.environ["OPENAI_API_KEY"] = "sk-8t4sGAakvPVKfFLn9801056499284a66B31aC07b1f9907F3"
os.environ["OPENAI_BASE_URL"] = "https://vip.apiyi.com/v1"

# os.environ["OPENAI_API_KEY"] = "sk-tiajbqis4UNo0bRu4frkaaLPWABbe2wTDlGCg9qymjXJf9Gq"
# os.environ["OPENAI_API_KEY"] = "sk-IUDWXcrvbtYiRrwLAyIZCVV05EFyPjkFA277EtFh6f3uQjZZ"
# os.environ["OPENAI_BASE_URL"] = "https://api.chatanywhere.tech/v1"

# os.environ["OPENAI_API_KEY"] = "sk-d4e50bd7e07747b4827611c28da95c23"
# os.environ["OPENAI_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# 结束

ADB_PATH = "C:/Users/neosunjz/AppData/Local/Android/Sdk/platform-tools/adb.exe"
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

async def main():
    _config = FairyConfig(adb_path=os.environ["ADB_PATH"],
                          model=CoreChatModelConfig(
                              model_name="deepseek-v3", # "gpt-4o-2024-11-20"
                              model_temperature=0,
                              model_info={"vision": True, "function_calling": True, "json_output": True},
                              api_base="https://vip.apiyi.com/v1",
                              api_key="sk-8t4sGAakvPVKfFLn9801056499284a66B31aC07b1f9907F3"
                          ),
                          rag_model=RAGChatModelConfig(
                              model_name="qwen-long",
                              model_temperature=0,
                              api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
                              api_key="sk-d4e50bd7e07747b4827611c28da95c23"
                          ),
                          rag_embed_model=RAGEmbedModelConfig(
                              model_name="intfloat/multilingual-e5-large-instruct"
                          ),
                          non_visual_mode=True)
    fairy = FairyCore(_config)
    ## await fairy.start("Please help me to delete all flower related images in the album and clear the recycle bin")
    await fairy.start("请帮我在美团外卖App上点一个汉堡王的汉堡，当前的应用是就是美团外卖App")

if __name__ == '__main__':
    asyncio.run(main())