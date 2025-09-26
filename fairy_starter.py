import argparse
import asyncio
import os

from Fairy.config.model_config import CoreChatModelConfig, RAGChatModelConfig, RAGEmbedModelConfig, ModelConfig
from Fairy.fairy import FairyCore
from Fairy.config.fairy_config import FairyConfig, FairyEnvConfig




async def main():
    _config = FairyEnvConfig()
    fairy = FairyCore(_config)
    ## await fairy.start("Please help me to delete all flower related images in the album and clear the recycle bin")
    # await fairy.start("请帮我在美团外卖App上点一个‘肯德基’的汉堡，当前的应用是就是美团外卖App")

    # parser = argparse.ArgumentParser(description="Fariy interactive multi-agent mobile assistant")
    # parser.add_argument('--task', type=str, help="The instructions to be executed.", required=True)
    # args = parser.parse_args()
    # await fairy.start(args.task)

    await fairy.start("请你帮我在麦当劳App中点一个麦香鱼汉堡，不要套餐，只点一个麦香鱼即可！")

    # await fairy.start("请在麦当劳帮我点一个汉堡")

if __name__ == '__main__':
    asyncio.run(main())