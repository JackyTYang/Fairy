from Fairy.tools.screen_perceptor.entity import ScreenPreceptionInfo


class FineGrainedVisualPerceptionInfo(ScreenPreceptionInfo):
    def __init__(self, width, height, perception_infos):

        keyboard_status = False
        for perception_info in perception_infos:
            if 'ADB Keyboard' in perception_info['text']:
                keyboard_status = True
        super().__init__(width, height, perception_infos, keyboard_status)

    def get_screen_info_prompt(self, extra_suffix=None):
        prompt = f"- Screen Information {extra_suffix}: \n"
        for clickable_info in self.infos:
            if clickable_info['text'] != "" and clickable_info['text'] != "icon: None" and clickable_info[
                'coordinates'] != (0, 0):
                prompt += f"{clickable_info['coordinates']}; {clickable_info['text']}\n"

        prompt += f"\n"

        prompt += f"- Keyboard Status {extra_suffix}: "\
                  f"{'The keyboard has been activated and you can type.' if self.keyboard_status else 'The keyboard has not been activated and you can not type.'}\n"\
                  f"\n"
        return prompt

    def get_screen_info_note_prompt(self, description_prefix):
        prompt = f"{description_prefix}, with a width and height of {self.width} and {self.height} pixels respectively.\n"
        prompt += f"To help understand the screenshot(s), we also provide information about the position of the text elements and icons in these/this screenshot(s) in the format (coordinates; content). The coordinates are [x, y], where x represents the horizontal pixel position (left to right) and y represents the vertical pixel position (top to bottom). Please note that these information may not be completely accurate, so please combine them with the screenshot(s) to better understand the information.\n"
        return prompt