from ..entity import ScreenPreceptionInfo


class AdaptiveSemanticScreenModelingInfo(ScreenPreceptionInfo):
    def __init__(self, width, height, perception_infos,keyboard_status):
        super().__init__(width, height, perception_infos, keyboard_status)

    def get_screen_info_prompt(self, extra_suffix=None):
        prompt = f"- Screen XML Information {extra_suffix}: \n"
        prompt += f"{self.infos[1]}\n\n"

        prompt += f"- Keyboard Status {extra_suffix}: " \
                  f"{'The keyboard has been activated and you can type.' if self.keyboard_status else 'The keyboard has not been activated and you can not type.'}\n" \
                  f"\n"
        return prompt

    def get_screen_info_note_prompt(self, description_prefix):
        prompt = f"{description_prefix}, with a width and height of {self.width} and {self.height} pixels respectively.\n"
        prompt += f"To help understand or imagine the screen, we provide Screen XML Information. The value of the center attribute is the center coordinates of the current element on the screen in the format [x, y]. \n"
        return prompt