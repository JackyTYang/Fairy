import os
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from PIL import Image
from loguru import logger
from Fairy.entity.info_entity import ScreenFileInfo
from paddlex import create_pipeline


def parse_bounds(bstr: str) -> tuple:
    nums = bstr.replace('][', ',').replace('[', '').replace(']', '').split(',')
    return tuple(map(int, nums))


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


class OCRFilterTool:
    """
    工具类：对 UI XML 中被遮挡或 OCR 识别不一致的节点进行过滤

    方法:
        filter(xml_str: str, screenshot_file_info: ScreenFileInfo, threshold: float) -> str
            输入:
                xml_str   - 待过滤的 UI 层级 XML 字符串
                screenshot_file_info - 对应的屏幕截图
                threshold - 文本相似度阈值（0~1），低于此值则视为遮挡，默认 0.5
            输出:
                过滤后的 XML 字符串
    """

    def __init__(self, pipeline=None):
        self.pipeline = create_pipeline(pipeline="OCR")

    def filter(self, xml_str: str, screenshot_file_info: ScreenFileInfo, threshold: float = 0.5) -> str:
        logger.bind(log_tag="fairy_sys").info("[OCR Filter] TASK in progress...")
        # 解析并构建树、父节点映射
        tree = ET.ElementTree(ET.fromstring(xml_str))
        root = tree.getroot()
        parent_map = {c: p for p in tree.iter() for c in p}

        # 收集带文本且有 bounds 的节点
        text_nodes = []
        for e in root.findall('.//node'):
            text = e.attrib.get('text', '').strip()
            bounds = e.attrib.get('bounds')
            class_name = e.attrib.get('class')
            if text and bounds and (class_name.endswith('TextView') or class_name.endswith('Button')):
                rect = parse_bounds(bounds)
                text_nodes.append({'elem': e, 'text': text, 'rect': rect})

        # 打开截图
        img = Image.open(screenshot_file_info.get_screenshot_fullpath())
        occluded = []

        # OCR 识别并判断遮挡
        temp_path = f"{screenshot_file_info.file_path}/{screenshot_file_info.get_screenshot_filename(no_type=True)}/"
        os.makedirs(temp_path, exist_ok=True)
        count = 0
        for n in text_nodes:
            x1, y1, x2, y2 = n['rect']
            crop = img.crop((x1, y1, x2, y2))
            path = os.path.join(temp_path, f"textview_{count}.png")
            crop.save(path)
            res = self.pipeline.predict(input=path,
                                        use_doc_orientation_classify=False,
                                        use_doc_unwarping=False,
                                        use_textline_orientation=False,
                                        text_det_limit_type='max'
                                        )
            count += 1
            ocr_texts = []
            for response in res:
                ocr_texts = response.get('rec_texts', '')
            ocr_text = ''.join(ocr_texts)
            if similar(n['text'], ocr_text) < threshold:
                occluded.append(n)

        # 收集需删除节点：遮挡节点及同父级区域内兄弟节点
        to_remove = set()
        for n in occluded:
            parent = parent_map.get(n['elem'])
            if not parent:
                continue
            to_remove.add(n['elem'])
            px1, py1, px2, py2 = n['rect']
            for child in list(parent):
                b = child.attrib.get('bounds')
                if not b:
                    continue
                cx1, cy1, cx2, cy2 = parse_bounds(b)
                cx, cy = (cx1 + cx2) // 2, (cy1 + cy2) // 2
                if px1 <= cx <= px2 and py1 <= cy <= py2:
                    to_remove.add(child)

        # 删除标记节点
        for elem in to_remove:
            parent = parent_map.get(elem)
            if parent:
                parent.remove(elem)

        # 返回过滤后的 XML
        logger.bind(log_tag="fairy_sys").info("[OCR Filter] TASK completed.")
        return ET.tostring(root, encoding='utf-8').decode('utf-8')
