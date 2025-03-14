class FineGrainedVisualPerceptionInfo:
    def __init__(self, width, height, perception_infos):
        self.width = width
        self.height = height
        self.infos = perception_infos

        self.keyboard_status = False
        for perception_info in perception_infos:
            if 'ADB Keyboard' in perception_info['text']:
                self.keyboard_status = True

