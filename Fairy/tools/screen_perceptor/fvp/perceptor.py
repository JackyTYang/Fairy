# --!-- This module refers to the open-source implementation of the MobileAgent series work
from copy import deepcopy

from Fairy.config.model_config import ModelConfig
from .entity import FineGrainedVisualPerceptionInfo
from .screen_icon_perception import ScreenIconPerception
from .screen_text_perception import ScreenTextPerception
from PIL import Image, ImageDraw
from Fairy.entity.info_entity import ScreenFileInfo
import logging
logging.getLogger().setLevel(logging.WARNING)

class FineGrainedVisualPerceptor:
    def __init__(self, visual_prompt_model_config: ModelConfig):
        self.screen_text_perception = ScreenTextPerception()
        self.screen_icon_perception = ScreenIconPerception(visual_prompt_model_config)


    def get_perception_infos(self, screenshot_file_info: ScreenFileInfo):
        width, height = Image.open(screenshot_file_info.get_screenshot_fullpath()).size
        perception_infos = []

        # Text Perception
        text_perception_infos, text_center_point_list = self.screen_text_perception.get_text_perception(screenshot_file_info)
        output_screenshot_file_info = self.draw_coordinates_on_image(screenshot_file_info, text_center_point_list)
        perception_infos.extend(text_perception_infos)

        # Icon Perception
        icon_perception_infos = self.screen_icon_perception.get_icon_perception(screenshot_file_info)
        perception_infos.extend(icon_perception_infos)

        for i in range(len(perception_infos)):
            perception_infos[i]['coordinates'] = [
                int((perception_infos[i]['coordinates'][0] + perception_infos[i]['coordinates'][2]) / 2),
                int((perception_infos[i]['coordinates'][1] + perception_infos[i]['coordinates'][3]) / 2)]

        return output_screenshot_file_info, FineGrainedVisualPerceptionInfo(width, height, perception_infos)

    def draw_coordinates_on_image(self, screenshot_file_info, coordinates):
        screenshot_file_info = deepcopy(screenshot_file_info)
        image = Image.open(screenshot_file_info.get_screenshot_fullpath())
        draw = ImageDraw.Draw(image)
        point_size = 10
        for coord in coordinates:
            draw.ellipse((coord[0] - point_size, coord[1] - point_size, coord[0] + point_size, coord[1] + point_size),
                         fill='red')
        screenshot_file_info.set_extra_name("_output")
        output_image_path = screenshot_file_info.get_screenshot_fullpath()
        image.save(output_image_path)
        return screenshot_file_info
