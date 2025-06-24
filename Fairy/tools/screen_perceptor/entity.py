import string
import random
from loguru import logger

class ScreenPreceptionInfo:
    def __init__(self, width, height, perception_infos, keyboard_status=None, use_set_of_marks_mapping=False):
        self.width = width
        self.height = height
        self.infos = perception_infos
        self.keyboard_status = keyboard_status

        self.use_set_of_marks_mapping = use_set_of_marks_mapping

        self.log_tag = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        logger.bind(log_tag="screen_perception").debug(f"Screen Info [{self.log_tag}]\n{self.infos}")

    def __str__(self):
        return (f"\n---Screen Perception Info---\n"
                f" - Use SoM Mapping: {self.use_set_of_marks_mapping}\n"
                f" - Screen Width: {self.width}\n"
                f" - Screen Height: {self.height}\n"
                f" - Screen Info: RECORDED IN THE LOG {self.log_tag}\n"
                f" - Keyboard Status: {self.keyboard_status}")

    def mark_to_coordinate_mapping_conversion(self, mark):
        ...

    def get_screen_info_prompt(self, extra_suffix=None):
        ...

    def get_screen_info_note_prompt(self, description_prefix):
        ...