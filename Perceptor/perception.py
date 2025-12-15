import asyncio
from Fairy.tools.screen_perceptor.ssip_new.perceptor.perceptor import ScreenStructuredInfoPerception
from Fairy.config.model_config import ModelConfig
from Fairy.entity.info_entity import ScreenFileInfo
from tools import UIAutomatorCapture


async def main():
    # 1. 捕获当前屏幕数据
    capturer = UIAutomatorCapture(
        adb_path="/Users/jackyyang/android_sdk/platform-tools/adb",
        output_dir="./captures"
    )
    capture_data = capturer.capture()

    print(f"已捕获数据:")
    print(f"  截图: {capture_data['screenshot_path']}")
    print(f"  XML: {capture_data['xml_path']}")
    print(f"  屏幕尺寸: {capture_data['screen_size']}")

    # 2. 配置视觉模型
    visual_model_config = ModelConfig(
        model_name="qwen3-vl-plus",
        model_temperature=0,
        model_info={"vision": True, "function_calling": False, "json_output": False},
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-0535d1b9e92c4c2085f23219330470a0"
    )

    # 3. 创建ScreenFileInfo对象
    import os
    from PIL import Image as PILImage

    # 确保使用绝对路径
    capture_folder_abs = os.path.abspath(capture_data['capture_folder'])

    # 创建 ScreenFileInfo（不覆盖方法，让它正常工作）
    screenshot_file_info = ScreenFileInfo(
        file_path=capture_folder_abs,
        file_name=f"screenshot",  # 基础名称
        file_type='png',
        file_build_timestamp=capture_data['timestamp']  # 使用时间戳字符串
    )

    # 获取原始截图应该保存的路径（带时间戳后缀）
    original_screenshot_save_path = screenshot_file_info.get_screenshot_fullpath()

    # 将捕获的截图移动/复制到正确的路径
    if os.path.abspath(capture_data['screenshot_path']) != original_screenshot_save_path:
        original_img = PILImage.open(capture_data['screenshot_path'])
        original_img.save(original_screenshot_save_path)
        print(f"原始截图已保存: {original_screenshot_save_path}")
        # 删除捕获时的临时文件
        if os.path.exists(capture_data['screenshot_path']) and capture_data['screenshot_path'] != original_screenshot_save_path:
            os.remove(capture_data['screenshot_path'])
    else:
        print(f"原始截图路径: {original_screenshot_save_path}")

    ui_xml = capture_data['ui_xml']

    # 4. 创建感知器（参考screen_perceptor.py）
    ssip = ScreenStructuredInfoPerception(visual_model_config, text_summarization_model_config=None)

    # 5. 获取感知信息（参考screen_perceptor.py:80）
    print("\n开始屏幕感知...")
    screenshot_file_info, perception_infos = await ssip.get_perception_infos(
        raw_screenshot_file_info=screenshot_file_info,
        ui_hierarchy_xml=ui_xml,
        non_visual_mode=False,  # 使用视觉模式（Set-of-Marks）
        target_app=None
    )

    # 6. 压缩XML（使用 XMLCompressor）
    print("\n开始压缩XML...")
    from tools import XMLCompressor
    compressor = XMLCompressor(output_dir=capture_data['capture_folder'])
    compressed_xml_path, compressed_txt_path = await compressor.compress_xml(
        ui_xml=ui_xml,
        timestamp=capture_data['timestamp'],
        target_app=None
    )

    # 7. 保存结果
    print("\n感知完成，保存结果...")
    import json

    # SoM映射
    som_mapping_path = os.path.join(capture_data['capture_folder'],
                                    f"som_mapping_{capture_data['timestamp']}.json")
    with open(som_mapping_path, 'w', encoding='utf-8') as f:
        json.dump(perception_infos.SoM_mapping, f, indent=2)

    print(f"\n✅ 所有文件已保存到: {capture_data['capture_folder']}")
    print(f"  📸 原始截图: {os.path.basename(original_screenshot_save_path)}")
    print(f"  🎯 标注截图: screenshot_{capture_data['timestamp']}_marked.png")
    print(f"  📄 原始XML: {os.path.basename(capture_data['xml_path'])}")
    print(f"  📦 压缩XML: {os.path.basename(compressed_xml_path)}")
    print(f"  📝 压缩TXT: {os.path.basename(compressed_txt_path)}")
    print(f"  🗺️  SoM映射: {os.path.basename(som_mapping_path)}")

    # 示例：显示前5个标记
    print(f"\n前5个SoM标记:")
    for mark_id in list(perception_infos.SoM_mapping.keys())[:5]:
        coords = perception_infos.convert_marks_to_coordinates(mark_id)
        print(f"  标记{mark_id}: {coords}")


if __name__ == "__main__":
    asyncio.run(main())
