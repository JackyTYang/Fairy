import asyncio
import os

from PIL.ImagePath import Path
from dotenv import load_dotenv

from Fairy.config.model_config import ModelConfig
from Fairy.tools.screen_perceptor.ssip_new.llm_tools.text_summarizer import TextSummarizer

load_dotenv(dotenv_path=Path('../../.env'))

async def test():
    ts = TextSummarizer(ModelConfig(
        model_name="qwen",
        api_base=os.getenv("ALI_API_BASE"),
        api_key=os.getenv("ALI_API_KEY"),
    ))
    print(await ts.summarize_text(["- Img (iv_bg) [The image is a promotional icon for a McDonald\'s \'My Gold Big Mac\' meal, showing a burger, fries, and a drink, with a price reduction from ¥60 to ¥31.]- Img (iv_food) [The image is a promotional graphic for McDonald\'s featuring a large burger, fries, and a soda, with the iconic golden arches logo in the background.]- Img (iv_label) [The image is a red promotional icon with the text '立省 ¥29' indicating a savings of 29 yen.]- LinearLayout- Txt (tv_label_price_prefix) [¥ ]- Txt (tv_label_price) [29 ]- Txt (tv_title) [My Gold Big Mac™ 4pc Combo]- Txt (tv_price) [¥31]- Txt (tv_separate_price) [¥60]"]))

if __name__ == '__main__':
    asyncio.run(test())