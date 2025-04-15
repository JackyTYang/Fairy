from .compressXML import is_keyboard_active
from ..entity import ScreenPreceptionInfo


class AdaptiveSemanticScreenModelingInfo(ScreenPreceptionInfo):
    def __init__(self, width, height, perception_infos,keyboard_status):
        super().__init__(width, height, perception_infos, keyboard_status)

    def get_screen_info_prompt(self, extra_suffix=None):
        prompt = f"- Screen XML Information {extra_suffix}: \n"
        prompt += f"{self.infos}\n\n"

        prompt += f"- Keyboard Status {extra_suffix}: " \
                  f"{'The keyboard has been activated and you can type.' if self.keyboard_status else 'The keyboard has not been activated and you can not type.'}\n" \
                  f"\n"
        return prompt

    def get_screen_info_note_prompt(self, description_prefix):
        prompt = f"{description_prefix}, with a width and height of {self.width} and {self.height} pixels respectively.\n"
        prompt += f"To help understand or imagine the screen, we provide Screen XML Information. The value of the bounds attribute is the coordinates of the current element on the screen in the format [x1, y1][x2, y2], where x represents the horizontal pixel position (from left to right) and y represents the vertical pixel position (from top to bottom). [x1, y1] represents the coordinates of the top-left vertex of the current element, and [x2, y2] represents the coordinates of the bottom-right vertex of the current element. To manipulate the element, click on its centre (usually [x2-x1, y2-y1]). \n"
        return prompt