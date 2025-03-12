import asyncio

from loguru import logger

from Fairy.fairy_config import Config
from Fairy.tools.screen_perception import ScreenPerception

ADB_PATH = "C:/Users/neosunjz/AppData/Local/Android/Sdk/platform-tools/adb.exe"

async def main():
    logger.debug("Running!")
    config = Config(ADB_PATH)
    screen_perception = ScreenPerception(config)
    result = await screen_perception.get_screen_description()
    print(result)

if __name__ == '__main__':
    asyncio.run(main())
