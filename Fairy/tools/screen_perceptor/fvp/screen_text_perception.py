# --!-- This module refers to the open-source implementation of the MobileAgent series work
import cv2
import numpy as np
from loguru import logger
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks
import math

class ScreenTextPerception:
    def __init__(self,
                 ocr_detection_model="iic/cv_resnet18_ocr-detection-db-line-level_damo",
                 ocr_recognition_model="iic/cv_convnextTiny_ocr-recognition-document_damo"):

        self.ocr_detection = pipeline(Tasks.ocr_detection, model=ocr_detection_model)  # dbnet (no tensorflow)
        self.ocr_recognition = pipeline(Tasks.ocr_recognition, model=ocr_recognition_model)

    def get_text_perception(self, screenshot_file_info):
        logger.bind(log_tag="fairy_sys").info("[Text Perception] TASK (including [Text Detection] and [Text Recognition]) in progress...")

        image = cv2.imread(screenshot_file_info.get_screenshot_fullpath())
        text, coordinates = self._ocr(image)
        text, coordinates = self._merge_text_blocks(text, coordinates)

        text_center_point_list = [[(coordinate[0] + coordinate[2]) / 2, (coordinate[1] + coordinate[3]) / 2] for coordinate in
                       coordinates]

        text_perception_infos = []
        for i in range(len(coordinates)):
            text_perception_info = {"text": "text: " + text[i], "coordinates": coordinates[i]}
            text_perception_infos.append(text_perception_info)

        return text_perception_infos, text_center_point_list

    def _ocr(self, image):
        text_data = []
        coordinate = []

        logger.bind(log_tag="fairy_sys").info("[Text Detection] TASK in progress...")
        det_result = self.ocr_detection(image)['polygons']
        logger.bind(log_tag="fairy_sys").info("[Text Detection] TASK completed.")

        logger.bind(log_tag="fairy_sys").info("[Text Recognition] TASK in progress...")
        for i in range(det_result.shape[0]):
            pts = self._order_point(det_result[i])
            image_crop = self._crop_image(image, pts)

            try:
                result = self.ocr_recognition(image_crop)['text'][0]
            except:
                continue

            box = [int(e) for e in list(pts.reshape(-1))]
            box = [box[0], box[1], box[4], box[5]]

            text_data.append(result)
            coordinate.append(box)

        else:
            logger.bind(log_tag="fairy_sys").info("[Text Recognition] TASK completed.")
            logger.bind(log_tag="fairy_sys").info("[Text Perception] TASK (including [Text Detection] and [Text Recognition]) completed.")
            return text_data, coordinate

    @staticmethod
    def _crop_image(img, position):
        def distance(x1, y1, x2, y2):
            return math.sqrt(pow(x1 - x2, 2) + pow(y1 - y2, 2))

        position = position.tolist()
        for i in range(4):
            for j in range(i + 1, 4):
                if (position[i][0] > position[j][0]):
                    tmp = position[j]
                    position[j] = position[i]
                    position[i] = tmp
        if position[0][1] > position[1][1]:
            tmp = position[0]
            position[0] = position[1]
            position[1] = tmp

        if position[2][1] > position[3][1]:
            tmp = position[2]
            position[2] = position[3]
            position[3] = tmp

        x1, y1 = position[0][0], position[0][1]
        x2, y2 = position[2][0], position[2][1]
        x3, y3 = position[3][0], position[3][1]
        x4, y4 = position[1][0], position[1][1]

        corners = np.zeros((4, 2), np.float32)
        corners[0] = [x1, y1]
        corners[1] = [x2, y2]
        corners[2] = [x4, y4]
        corners[3] = [x3, y3]

        img_width = distance((x1 + x4) / 2, (y1 + y4) / 2, (x2 + x3) / 2, (y2 + y3) / 2)
        img_height = distance((x1 + x2) / 2, (y1 + y2) / 2, (x4 + x3) / 2, (y4 + y3) / 2)

        corners_trans = np.zeros((4, 2), np.float32)
        corners_trans[0] = [0, 0]
        corners_trans[1] = [img_width - 1, 0]
        corners_trans[2] = [0, img_height - 1]
        corners_trans[3] = [img_width - 1, img_height - 1]

        transform = cv2.getPerspectiveTransform(corners, corners_trans)
        dst = cv2.warpPerspective(img, transform, (int(img_width), int(img_height)))
        return dst

    @staticmethod
    def _order_point(coor):
        arr = np.array(coor).reshape([4, 2])
        sum_ = np.sum(arr, 0)
        centroid = sum_ / arr.shape[0]
        theta = np.arctan2(arr[:, 1] - centroid[1], arr[:, 0] - centroid[0])
        sort_points = arr[np.argsort(theta)]
        sort_points = sort_points.reshape([4, -1])
        if sort_points[0][0] > centroid[0]:
            sort_points = np.concatenate([sort_points[3:], sort_points[:3]])
        sort_points = sort_points.reshape([4, 2]).astype('float32')
        return sort_points

    @staticmethod
    def _merge_text_blocks(
            text_list,
            coordinates_list,
            x_distance_threshold=45,
            y_distance_min=-20,
            y_distance_max=30,
            height_difference_threshold=20,
    ):
        merged_text_blocks = []
        merged_coordinates = []

        # Sort the text blocks based on y and x coordinates
        sorted_indices = sorted(
            range(len(coordinates_list)),
            key=lambda k: (coordinates_list[k][1], coordinates_list[k][0]),
        )
        sorted_text_list = [text_list[i] for i in sorted_indices]
        sorted_coordinates_list = [coordinates_list[i] for i in sorted_indices]

        num_blocks = len(sorted_text_list)
        merge = [False] * num_blocks

        for i in range(num_blocks):
            if merge[i]:
                continue

            anchor = i
            group_text = [sorted_text_list[anchor]]
            group_coordinates = [sorted_coordinates_list[anchor]]

            for j in range(i + 1, num_blocks):
                if merge[j]:
                    continue

                # Calculate differences and thresholds
                x_diff_left = abs(sorted_coordinates_list[anchor][0] - sorted_coordinates_list[j][0])
                x_diff_right = abs(sorted_coordinates_list[anchor][2] - sorted_coordinates_list[j][2])

                y_diff = sorted_coordinates_list[j][1] - sorted_coordinates_list[anchor][3]
                height_anchor = sorted_coordinates_list[anchor][3] - sorted_coordinates_list[anchor][1]
                height_j = sorted_coordinates_list[j][3] - sorted_coordinates_list[j][1]
                height_diff = abs(height_anchor - height_j)

                if (
                        (x_diff_left + x_diff_right) / 2 < x_distance_threshold
                        and y_distance_min <= y_diff < y_distance_max
                        and height_diff < height_difference_threshold
                ):
                    group_text.append(sorted_text_list[j])
                    group_coordinates.append(sorted_coordinates_list[j])
                    merge[anchor] = True
                    anchor = j
                    merge[anchor] = True

            merged_text = "\n".join(group_text)
            min_x1 = min(group_coordinates, key=lambda x: x[0])[0]
            min_y1 = min(group_coordinates, key=lambda x: x[1])[1]
            max_x2 = max(group_coordinates, key=lambda x: x[2])[2]
            max_y2 = max(group_coordinates, key=lambda x: x[3])[3]

            merged_text_blocks.append(merged_text)
            merged_coordinates.append([min_x1, min_y1, max_x2, max_y2])
        return merged_text_blocks, merged_coordinates