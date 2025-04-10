class AdaptiveSemanticScreenModelingInfo:
    def __init__(self, width, height, perception_infos):
        self.width = width
        self.height = height
        self.infos = perception_infos

        self.keyboard_status = False

    def __str__(self):
        return f"AdaptiveSemanticScreenModelingInfo: {self.width}, {self.height}, {self.infos}, {self.keyboard_status}"

    def get_screen_info_prompt(self, extra_suffix=None):
        prompt = ""
        return prompt

    def get_screen_info_note_prompt(self, description_prefix):
        prompt = ""
        return prompt