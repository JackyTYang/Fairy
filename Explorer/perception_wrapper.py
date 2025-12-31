"""
屏幕感知封装模块

封装Perceptor的调用，提供统一的接口
"""

import asyncio
import os
from pathlib import Path
from PIL import Image as PILImage

from Fairy.tools.screen_perceptor.ssip_new.perceptor.perceptor import ScreenStructuredInfoPerception
from Fairy.config.model_config import ModelConfig
from Fairy.entity.info_entity import ScreenFileInfo

from Perceptor.tools import UIAutomatorCapture, XMLCompressor

from .entities import PerceptionOutput
from .logger import get_logger

logger = get_logger("PerceptionWrapper")


class PerceptionWrapper:
    """屏幕感知封装器

    封装Perceptor模块的调用，提供统一的接口

    Examples:
        wrapper = PerceptionWrapper(
            visual_model_config=model_config,
            adb_path="/path/to/adb",
            output_dir="./captures"
        )
        perception_output = await wrapper.capture_and_perceive()
    """

    def __init__(
        self,
        visual_model_config: ModelConfig,
        adb_path: str,
        output_dir: str,
        device_id: str = None
    ):
        """
        Args:
            visual_model_config: 视觉模型配置
            adb_path: ADB路径
            output_dir: 输出目录
            device_id: 设备ID
        """
        self.visual_model_config = visual_model_config
        self.adb_path = adb_path
        self.output_dir = Path(output_dir)
        self.device_id = device_id

        # 创建屏幕感知器
        self.ssip = ScreenStructuredInfoPerception(
            visual_model_config,
            text_summarization_model_config=None
        )

        logger.info(f"PerceptionWrapper初始化完成")

    async def capture_and_perceive(
        self,
        non_visual_mode: bool = False,
        target_app: str = None
    ) -> PerceptionOutput:
        """捕获并感知当前屏幕

        执行完整的屏幕感知流程：
        1. 捕获屏幕（截图 + XML）
        2. 视觉感知（SoM标记）
        3. XML压缩
        4. 保存所有输出文件

        Args:
            non_visual_mode: 是否使用非视觉模式（不使用SoM）
            target_app: 目标应用包名（可选）

        Returns:
            PerceptionOutput: 包含所有输出文件路径的对象
        """
        logger.info("开始捕获和感知屏幕...")

        # 1. 捕获当前屏幕（使用单例 uiautomator2）
        logger.debug("捕获屏幕数据...")
        capturer = UIAutomatorCapture(
            adb_path=self.adb_path,
            output_dir=str(self.output_dir),
            use_singleton=True,  # 使用单例模式
            device_id=self.device_id
        )
        capture_data = capturer.capture()

        logger.debug(f"截图路径: {capture_data['screenshot_path']}")
        logger.debug(f"XML路径: {capture_data['xml_path']}")
        logger.debug(f"屏幕尺寸: {capture_data['screen_size']}")

        # 2. 创建 ScreenFileInfo
        capture_folder_abs = os.path.abspath(capture_data['capture_folder'])
        screenshot_file_info = ScreenFileInfo(
            file_path=capture_folder_abs,
            file_name="screenshot",
            file_type='png',
            file_build_timestamp=capture_data['timestamp']
        )

        # 保存原始截图
        original_screenshot_path = screenshot_file_info.get_screenshot_fullpath()
        if os.path.abspath(capture_data['screenshot_path']) != original_screenshot_path:
            original_img = PILImage.open(capture_data['screenshot_path'])
            original_img.save(original_screenshot_path)
            logger.debug(f"原始截图已保存: {original_screenshot_path}")
            # 删除临时文件
            if os.path.exists(capture_data['screenshot_path']) and \
               capture_data['screenshot_path'] != original_screenshot_path:
                os.remove(capture_data['screenshot_path'])

        ui_xml = capture_data['ui_xml']

        # 3. 屏幕感知（SoM标记）
        logger.info("执行屏幕感知...")
        screenshot_file_info, perception_infos = await self.ssip.get_perception_infos(
            raw_screenshot_file_info=screenshot_file_info,
            ui_hierarchy_xml=ui_xml,
            non_visual_mode=non_visual_mode,
            target_app=target_app
        )

        # 4. 压缩XML (仅用于生成旧格式的compressed_xml，compressed_txt改用som_compressed_txt)
        logger.debug("压缩XML...")
        compressor = XMLCompressor(output_dir=capture_data['capture_folder'])
        compressed_xml_path, _ = await compressor.compress_xml(
            ui_xml=ui_xml,
            timestamp=capture_data['timestamp'],
            target_app=target_app
        )

        # 5. 保存SoM映射和对应的compressed文本（确保索引一致）
        import json
        som_mapping_path = os.path.join(
            capture_data['capture_folder'],
            f"som_mapping_{capture_data['timestamp']}.json"
        )
        with open(som_mapping_path, 'w', encoding='utf-8') as f:
            json.dump(perception_infos.SoM_mapping, f, indent=2)

        # ⭐ 保存与SoM_mapping索引对应的compressed文本
        compressed_txt_path = os.path.join(
            capture_data['capture_folder'],
            f"compressed_{capture_data['timestamp']}.txt"
        )
        with open(compressed_txt_path, 'w', encoding='utf-8') as f:
            f.write(perception_infos.som_compressed_txt if perception_infos.som_compressed_txt else "")

        # 6. 构建输出对象
        marked_screenshot_path = screenshot_file_info.get_screenshot_fullpath()

        perception_output = PerceptionOutput(
            screenshot_path=original_screenshot_path,
            marked_screenshot_path=marked_screenshot_path,
            xml_path=capture_data['xml_path'],
            compressed_xml_path=compressed_xml_path,
            compressed_txt_path=compressed_txt_path,
            som_mapping_path=som_mapping_path,
            timestamp=capture_data['timestamp'],
            screen_size=capture_data['screen_size']
        )

        logger.success(f"屏幕感知完成，输出目录: {capture_data['capture_folder']}")

        return perception_output
