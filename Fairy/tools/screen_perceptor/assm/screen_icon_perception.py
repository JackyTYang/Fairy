import concurrent
import os
import re

from loguru import logger
from PIL import Image
from dashscope import MultiModalConversation

from Fairy.info_entity import ScreenFileInfo
from Fairy.tools.screen_perceptor.assm.compressXML import parse_bounds
import xml.etree.ElementTree as ET


def extract_icons_and_attach_id(root, screenshot_path, output_img_dir):
    os.makedirs(output_img_dir, exist_ok=True)
    image = Image.open(screenshot_path)
    count = 0
    # 找到所有 ImageView
    # 注意：在 uiautomator2 的 dump 里，所有控件标签都是 <node>
    image_nodes = root.findall(".//node[@class='android.widget.ImageView']")
    for node in image_nodes:
        bounds = node.attrib.get("bounds", "")
        if not bounds:
            continue
        x1, y1, x2, y2 = parse_bounds(bounds)
        if x2 > x1 and y2 > y1:
            cropped = image.crop((x1, y1, x2, y2))
            fname = f"imageview_{count}.png"
            cropped.save(os.path.join(output_img_dir, fname))
            node.attrib["image-id"] = count
            count += 1
    # print(f"🎉 图标提取完成，共保存 {count} 张图标。")


# ----- XML 注入描述 -----
def annotate_xml_with_descriptions(root, desc_map):
    image_nodes = root.findall(".//node[@class='android.widget.ImageView']")
    for node in image_nodes:
        img_id = node.attrib.pop('image-id', None)
        if img_id in desc_map:
            node.attrib['image-desc'] = desc_map[img_id]
    # print(f"✅ 已将 image-desc 注入 XML")
    return ET.tostring(root, encoding='utf-8').decode('utf-8')


class ScreenIconPerception:
    def __init__(self,
                 caption_model="qwen-vl-plus",
                 caption_model_api_key="sk-d4e50bd7e07747b4827611c28da95c23"):
        self.caption_model = caption_model
        self.caption_model_api_key = caption_model_api_key

    def get_icon_perception(self, screenshot_file_info: ScreenFileInfo, ui_hierarchy_xml):
        logger.bind(log_tag="fairy_sys").info("[Icon Perception] TASK in progress...")
        root = ET.fromstring(ui_hierarchy_xml)
        icon_temp_path = f"{screenshot_file_info.file_path}/{screenshot_file_info.get_screenshot_filename(no_type=True)}/"
        os.makedirs(icon_temp_path, exist_ok=True)
        extract_icons_and_attach_id(root, screenshot_file_info.get_screenshot_fullpath(), icon_temp_path)

        files = os.listdir(icon_temp_path)
        images = [f for f in files if f.startswith('imageview_')]
        if len(images) > 0:
            pattern = re.compile(r'_(\d+)\.')
            images = sorted(images,key=lambda x: int(pattern.search(x).group(1)))
            prompt = 'This image is an icon from a phone screen. Please briefly describe this icon in one sentence.'

            for i in range(len(images)):
                images[i] = os.path.join(icon_temp_path, images[i])
            desc_map = self._generate_api(images, prompt)
            ui_hierarchy_xml = annotate_xml_with_descriptions(root, desc_map)
        logger.bind(log_tag="fairy_sys").info("[Icon Perception] TASK completed.")
        return ui_hierarchy_xml

    def _generate_api(self, images, query):
        icon_map = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(self._process_image, image, query): i for i, image in
                       enumerate(images)}

            for future in concurrent.futures.as_completed(futures):
                i = futures[future]
                response = future.result()
                icon_map[i] = response

        return icon_map

    def _process_image(self, image, query):
        image_path = f"file://{os.path.abspath(image)}"
        messages = [{'role': 'user',
                     'content': [{'image': image_path},
                                 {'text': query}]}]
        response = MultiModalConversation.call(api_key=self.caption_model_api_key,
                                               model=self.caption_model,
                                               messages=messages)
        try:
            response = response['output']['choices'][0]['message']['content'][0]["text"]
        except:
            response = "This is an icon."
        return response
