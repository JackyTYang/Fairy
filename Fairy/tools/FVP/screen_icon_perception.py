# --!-- This module refers to the open-source implementation of the MobileAgent series work
import os

import torch
from loguru import logger
from modelscope import snapshot_download
from modelscope.pipelines import pipeline
from PIL import Image
import concurrent

from dashscope import MultiModalConversation
import dashscope

from Fairy.info_entity import ScreenFileInfo


class ScreenIconPerception:
    def __init__(self,
                 groundingdino_model="AI-ModelScope/GroundingDINO",
                 groundingdino_revision="v1.0.0",
                 caption_model="qwen-vl-plus",
                 caption_model_api_key="sk-d4e50bd7e07747b4827611c28da95c23"):
        groundingdino_dir = snapshot_download(groundingdino_model, revision=groundingdino_revision)
        self.groundingdino_model = pipeline('grounding-dino-task', model=groundingdino_dir)
        self.caption_model = caption_model
        self.caption_model_api_key = caption_model_api_key

    def get_icon_perception(self, screenshot_file_info: ScreenFileInfo):
        logger.debug("Icon Perception task (including Icon Recognition and Icon Description) in progress...")

        logger.debug("Icon Recognition task in progress...")
        image_boxs = self._det(screenshot_file_info.get_screenshot_fullpath())
        logger.debug("Icon Recognition task completed.")

        logger.debug("Icon Description task in progress...")
        image_id = range(len(image_boxs))
        icon_perception_infos = []
        for i in range(len(image_boxs)):
            perception_info = {"text": "icon", "coordinates": image_boxs[i]}
            icon_perception_infos.append(perception_info)

        icon_temp_path = f"{screenshot_file_info.file_path}/{screenshot_file_info.get_screenshot_filename(no_type=True)}/"
        os.makedirs(icon_temp_path, exist_ok=True)

        images = []
        for i in range(len(image_boxs)):
            image = self._crop(screenshot_file_info.get_screenshot_fullpath(), image_boxs[i])
            if image is not None:
                save_path = os.path.join(icon_temp_path, f"{image_id[i]}.png")
                image.save(save_path)
                images.append(f"{image_id[i]}.png")

        if len(images) > 0:

            images = sorted(images, key=lambda x: int(x.split('/')[-1].split('.')[0]))
            image_id = [int(image.split('/')[-1].split('.')[0]) for image in images]

            prompt = 'This image is an icon from a phone screen. Please briefly describe the shape and color of this icon in one sentence.'

            for i in range(len(images)):
                images[i] = os.path.join(icon_temp_path, images[i])
            icon_map = self._generate_api(images, prompt)

            logger.debug("Icon Description task completed.")

            for i, j in zip(image_id, range(1, len(image_id) + 1)):
                if icon_map.get(j):
                    icon_perception_infos[i]['text'] = "icon: " + icon_map[j]

        return icon_perception_infos

    def _crop(self, image, box):
        image = Image.open(image)
        x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
        if x1 >= x2 - 10 or y1 >= y2 - 10:
            return None
        cropped_image = image.crop((x1, y1, x2, y2))
        return cropped_image

    def _generate_api(self, images, query):
        icon_map = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(self._process_image, image, query): i for i, image in
                       enumerate(images)}

            for future in concurrent.futures.as_completed(futures):
                i = futures[future]
                response = future.result()
                icon_map[i + 1] = response

        return icon_map

    def _process_image(self, image, query):
        dashscope.api_key = self.caption_model_api_key
        image = "file://" + image
        messages = [{'role':'user','content':[{'image':image},{'text':query}]}]
        response = MultiModalConversation.call(model=self.caption_model, messages=messages)
        try:
            response = response['output']['choices'][0]['message']['content'][0]["text"]
        except:
            response = "This is an icon."
        return response

    def _det(self, image_path, caption="icon", box_threshold=0.05, text_threshold=0.5):
        image = Image.open(image_path)
        size = image.size

        caption = caption.lower()
        caption = caption.strip()
        if not caption.endswith('.'):
            caption = caption + '.'

        # https://modelscope.cn/models/AI-ModelScope/GroundingDINO
        # Request to provide image path.
        inputs = {
            'IMAGE_PATH': image_path,
            'TEXT_PROMPT': caption,
            'BOX_TRESHOLD': box_threshold,
            'TEXT_TRESHOLD': text_threshold
        }

        result = self.groundingdino_model(inputs)
        boxes_filt = result['boxes']

        H, W = size[1], size[0]
        for i in range(boxes_filt.size(0)):
            boxes_filt[i] = boxes_filt[i] * torch.Tensor([W, H, W, H])
            boxes_filt[i][:2] -= boxes_filt[i][2:] / 2
            boxes_filt[i][2:] += boxes_filt[i][:2]

        boxes_filt = boxes_filt.cpu().int().tolist()
        filtered_boxes = self._remove_boxes(boxes_filt, size)  # [:9]
        coordinates = []
        for box in filtered_boxes:
            coordinates.append([box[0], box[1], box[2], box[3]])

        return coordinates

    def _remove_boxes(self, boxes_filt, size, iou_threshold=0.5):
        boxes_to_remove = set()

        for i in range(len(boxes_filt)):
            if self._calculate_size(boxes_filt[i]) > 0.05 * size[0] * size[1]:
                boxes_to_remove.add(i)
            for j in range(len(boxes_filt)):
                if self._calculate_size(boxes_filt[j]) > 0.05 * size[0] * size[1]:
                    boxes_to_remove.add(j)
                if i == j:
                    continue
                if i in boxes_to_remove or j in boxes_to_remove:
                    continue
                iou = self._calculate_iou(boxes_filt[i], boxes_filt[j])
                if iou >= iou_threshold:
                    boxes_to_remove.add(j)

        boxes_filt = [box for idx, box in enumerate(boxes_filt) if idx not in boxes_to_remove]

        return boxes_filt

    @staticmethod
    def _calculate_size(box):
        return (box[2] - box[0]) * (box[3] - box[1])

    @staticmethod
    def _calculate_iou(box1, box2):
        xA = max(box1[0], box2[0])
        yA = max(box1[1], box2[1])
        xB = min(box1[2], box2[2])
        yB = min(box1[3], box2[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        box1Area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2Area = (box2[2] - box2[0]) * (box2[3] - box2[1])
        unionArea = box1Area + box2Area - interArea
        iou = interArea / unionArea

        return iou