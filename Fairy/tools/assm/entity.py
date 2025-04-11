from .compressXML import is_keyboard_active
class AdaptiveSemanticScreenModelingInfo:
    def __init__(self, width, height, perception_infos):
        self.width = width
        self.height = height
        self.infos = perception_infos

        self.keyboard_status = is_keyboard_active(perception_infos,height)



    def __str__(self):
        return f"AdaptiveSemanticScreenModelingInfo: {self.width}, {self.height}, {self.infos}, {self.keyboard_status}"

    def get_screen_info_prompt(self, extra_suffix=None):
        prompt = f"- Screen XML Information {extra_suffix}: \n"
        prompt += f"{self.infos}\n"

        prompt += f"- Keyboard Status {extra_suffix}: " \
                  f"{'The keyboard has been activated and you can type.' if self.keyboard_status else 'The keyboard has not been activated and you can not type.'}\n" \
                  f"\n"
        return prompt

    def get_screen_info_note_prompt(self, description_prefix):
        prompt = f"{description_prefix}, with a width and height of {self.width} and {self.height} pixels respectively.\n"
        with open("tools/assm/prompt/XMLLattr.txt", "r", encoding="utf-8") as f:
            XMLLattr = f.read()  # 读取
        prompt += f"To help understand the screen, we provide compressed screen xml information, the xml attribute information is as follows: {XMLLattr}\n"
        return prompt