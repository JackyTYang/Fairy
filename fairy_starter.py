import argparse
import asyncio

from Fairy.fairy import FairyCore
from Fairy.config.fairy_config import FairyEnvConfig

async def main():
    _config = FairyEnvConfig()
    fairy = FairyCore(_config)

    parser = argparse.ArgumentParser(description="Fariy interactive multi-agent mobile assistant")
    parser.add_argument('--task', type=str, help="The instructions to be executed.", required=True)
    args = parser.parse_args()
    await fairy.start(args.task)

if __name__ == '__main__':
    asyncio.run(main())