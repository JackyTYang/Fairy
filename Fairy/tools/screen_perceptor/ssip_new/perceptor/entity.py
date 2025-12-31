from Fairy.tools.screen_perceptor.entity import ScreenPerceptionInfo


class SSIPInfo(ScreenPerceptionInfo):
    def __init__(self, width, height, perception_infos, non_visual_mode, SoM_mapping, som_compressed_txt=None):
        self.non_visual_mode = non_visual_mode
        self.SoM_mapping = SoM_mapping
        self.som_compressed_txt = som_compressed_txt  # 与SoM_mapping索引对应的compressed文本

        super().__init__(width, height, perception_infos, use_set_of_marks_mapping=not self.non_visual_mode)

    def _perception_infos_to_str(self):
        return f"- Raw UI Hierarchy XML:\n"\
               f"{self.infos[0]}\n\n" \
               f"- Page Description:\n" \
               f"{self.infos[1]}\n\n"

    def _keyboard_prompt(self, extra_suffix=None):
        prompt = f"- Keyboard Status {'for '+extra_suffix if extra_suffix else ''}: " \
                 f"{'The keyboard has been activated and you can type.' if self.keyboard_status else 'The keyboard has not been activated and you can not type.'}\n" \
                 f"\n"
        return prompt

    def convert_marks_to_coordinates(self, mark):
        return self.SoM_mapping.get(mark, None)

    def get_screen_info_prompt(self, extra_suffix=None):
        prompt = ""

        # ⭐ 新增：在视觉模式下也提供SoM元素列表（混合模式）
        if not self.non_visual_mode and self.som_compressed_txt:
            prompt += f"## Marked Elements List {'for '+extra_suffix if extra_suffix else ''}\n"
            prompt += f"Below is the list of all marked elements with their text content, resource ID, and position:\n\n"
            prompt += f"{self.som_compressed_txt}\n\n"
            prompt += f"**Note**: Use the Mark number to select elements. The text content helps you identify the correct element.\n\n"

        # 原有的非视觉模式文本描述
        if self.non_visual_mode:
            prompt += f"- Screen Structure Textualized Description {'for '+extra_suffix if extra_suffix else ''}: \n"
            prompt += f"{self.infos[1]}\n\n"

        prompt += self._keyboard_prompt(extra_suffix)

        return prompt

    def get_screen_info_note_prompt(self, description_prefix):
        prompt = f"{description_prefix}, with a width and height of {self.width} and {self.height} pixels respectively.\n"
        if self.non_visual_mode:
            prompt += f"To help imagine the screen, we provide Structure Textualized Description about the screen, which is written as a sort of Markdown. For scrollable and clickable elements, we provide the center attribute, whose value is the center coordinates of the current element on the screen in the format [x, y]: \n"
        else:
            prompt += f"We have provided an image of the screen and labeled all clickable elements using red boxes with numbers in the upper left corner. For scrollable areas, we mark them with green boxes with numbers in the upper right corner.\n"
            prompt += f"Additionally, we provide a detailed list of all marked elements with their text content and resource IDs to help you identify the correct element more accurately.\n"
            prompt += f"**Please use the Mark number (not coordinates) to indicate which element you want to interact with.**\n"
        return prompt