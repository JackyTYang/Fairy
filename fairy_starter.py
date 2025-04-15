import asyncio
import os

from Fairy.fairy import FairyCore
from Fairy.fairy_config import FairyConfig

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

async def main():
    # _config = FairyConfig(adb_path=os.environ["ADB_PATH"], model="gpt-4o-2024-11-20", model_temperature=0, non_visual_mode=True)
    _config = FairyConfig(adb_path=os.environ["ADB_PATH"], model="deepseek-v3", model_temperature=0,
                               model_info={"vision": True, "function_calling": True, "json_output": True},
                               non_visual_mode=True)
    fairy = FairyCore(_config)
    ## await fairy.start("Please help me to delete all flower related images in the album and clear the recycle bin")
    await fairy.start("请帮我在美团外卖App上点一个肯德基的汉堡，当前的应用是就是美团外卖App")

if __name__ == '__main__':
    asyncio.run(main())

