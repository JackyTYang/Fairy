import base64
import concurrent
import os
import re

from loguru import logger
from PIL import Image
from openai import OpenAI

from Fairy.config.model_config import ModelConfig
from Fairy.info_entity import ScreenFileInfo
from Fairy.tools.screen_perceptor.ssip.compressXML import parse_bounds
import xml.etree.ElementTree as ET


def extract_icons_and_attach_id(root, screenshot_path, output_img_dir):
    os.makedirs(output_img_dir, exist_ok=True)
    image = Image.open(screenshot_path)
    count = 0
    # 找到所有 ImageView，在 uiautomator2 的 dump 里，所有控件标签都是 <node>
    image_nodes = root.findall(".//node[@class='android.widget.ImageView']")
    for node in image_nodes:
        bounds = node.attrib.get("bounds", "")
        if not bounds:
            continue
        x1, y1, x2, y2 = parse_bounds(bounds)
        if x2 > x1 and y2 > y1:
            cropped = image.crop((x1, y1, x2, y2))
            # 确保宽度和高度均大于10像素，否则等比例放大
            w, h = cropped.size
            if w <= 10 or h <= 10:
                # 目标尺寸需大于10像素，取11像素为下限
                scale = max(11 / w, 11 / h)
                new_w = int(w * scale)
                new_h = int(h * scale)
                cropped = cropped.resize((new_w, new_h), Image.LANCZOS)
            fname = f"imageview_{count}.png"
            cropped.save(os.path.join(output_img_dir, fname))
            node.attrib["image-id"] = count
            count += 1


# ----- XML 注入描述 -----
def annotate_xml_with_descriptions(root, desc_map):
    image_nodes = root.findall(".//node[@class='android.widget.ImageView']")
    for node in image_nodes:
        img_id = node.attrib.pop('image-id', None)
        if img_id in desc_map:
            node.attrib['image-desc'] = desc_map[img_id]
    return ET.tostring(root, encoding='utf-8').decode('utf-8')


#  base 64 编码格式
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


class ScreenIconPerception:
    def __init__(self, visual_prompt_model_config: ModelConfig):
        self.model = visual_prompt_model_config.model_name
        self.client = OpenAI(
            api_key=visual_prompt_model_config.api_key,
            base_url=visual_prompt_model_config.api_base,
        )

    def get_icon_perception(self, screenshot_file_info: ScreenFileInfo, ui_hierarchy_xml):
        logger.bind(log_tag="fairy_sys").info("[Image Perception] TASK in progress...")
        root = ET.fromstring(ui_hierarchy_xml)
        image_temp_path = f"{screenshot_file_info.file_path}/{screenshot_file_info.get_screenshot_filename(no_type=True)}/"
        os.makedirs(image_temp_path, exist_ok=True)
        extract_icons_and_attach_id(root, screenshot_file_info.get_screenshot_fullpath(), image_temp_path)

        files = os.listdir(image_temp_path)
        images = [f for f in files if f.startswith('imageview_')]
        if len(images) > 0:
            pattern = re.compile(r'_(\d+)\.')
            images = sorted(images,key=lambda x: int(pattern.search(x).group(1)))
            prompt = 'This image is an icon/image from a phone screen. Please briefly describe this icon/image in one sentence.'

            for i in range(len(images)):
                images[i] = os.path.join(image_temp_path, images[i])
            desc_map = self._build_requests(images, prompt)
            ui_hierarchy_xml = annotate_xml_with_descriptions(root, desc_map)
        logger.bind(log_tag="fairy_sys").info("[Image Perception] TASK completed.")
        return ui_hierarchy_xml

    def _build_requests(self, images, query):
        icon_map = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(self._build_single_request, image, query): i for i, image in
                       enumerate(images)}

            for future in concurrent.futures.as_completed(futures):
                i = futures[future]
                response = future.result()
                icon_map[i] = response

        return icon_map

    def _build_single_request(self, image, query):
        base64_image = encode_image(os.path.abspath(image))
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                            },
                            {"type": "text", "text": query},
                        ],
                    }
                ],
            )
            response = response.choices[0].message.content
        except Exception as e:
            logger.bind(log_tag="fairy_sys").warning(
                f"[Image Perception] Image Perception FAILS and returns the default result, reason: {e}")
            response = "This is an icon."
        return response
