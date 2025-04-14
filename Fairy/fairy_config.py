from Citlali.models.openai.client import OpenAIChatClient


class FairyConfig:
    def __init__(self,
                 model,
                 adb_path,
                 model_info=None,
                 model_temperature=0,
                 temp_path=None,
                 screenshot_phone_path=None,
                 screenshot_filename=None,
                 action_executor_type=None,
                 screenshot_getter_type=None,
                 screen_perception_type=None,
                 non_visual_mode=None):
        _model_config = {
            'model': model,
            'temperature': model_temperature
        }
        if model_info is not None:
            _model_config['model_info'] = model_info

        self.model_client = OpenAIChatClient(_model_config)

        # self._model_client = OpenAIChatClient({
        #     'model': "deepseek-v3",
        #     'model_info': {
        #         "vision": True,
        #         "function_calling": True,
        #         "json_output": True,
        #     },
        #     'temperature': 0
        # })

        self._adb_path = adb_path
        self.device = None

        # path of local temporary storage
        self.temp_path = "tmp" if temp_path is None else temp_path

        # path of screenshot storage on mobile phone
        self.screenshot_phone_path = "/sdcard" if screenshot_phone_path is None else screenshot_phone_path

        # filename of screenshot
        self.screenshot_filename = "screenshot" if screenshot_filename is None else screenshot_filename

        # execution strategy
        self.action_executor_type = "uiautomator" if action_executor_type is None else action_executor_type # default action executor type
        self.screenshot_getter_type = "uiautomator" if screenshot_getter_type is None else screenshot_getter_type  # default screenshot getter type
        self.screen_perception_type = "assm" if screen_perception_type is None else screen_perception_type # default screen_perception_type
        self.non_visual_mode = False if non_visual_mode is None else non_visual_mode

    def get_screenshot_temp_path(self):
        return self.temp_path + "/screenshot"

    def get_log_temp_path(self):
        return self.temp_path + "/log"

    def get_adb_path(self):
        return (self._adb_path + f" -s {self.device}") if self.device is not None else self._adb_path