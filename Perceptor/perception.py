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

    # 3. 创建ScreenFileInfo对象（参考Fairy的实现）
    import os
    screenshot_file_info = ScreenFileInfo(
        file_path=os.path.dirname(capture_data['screenshot_path']),
        file_name=os.path.basename(capture_data['screenshot_path']).rsplit('.', 1)[0],
        file_type='png'
    )
    # 覆盖路径方法使用已捕获的文件
    screenshot_file_info.get_screenshot_fullpath = lambda: capture_data['screenshot_path']

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

    # 6. 保存结果
    print("\n感知完成，保存结果...")
    import json

    # 原始XML
    raw_xml_path = os.path.join(os.path.dirname(capture_data['screenshot_path']),
                                f"raw_ui_{capture_data['timestamp']}.xml")
    with open(raw_xml_path, 'w', encoding='utf-8') as f:
        f.write(perception_infos.infos[0])

    # SoM映射
    som_mapping_path = os.path.join(os.path.dirname(capture_data['screenshot_path']),
                                    f"som_mapping_{capture_data['timestamp']}.json")
    with open(som_mapping_path, 'w', encoding='utf-8') as f:
        json.dump(perception_infos.SoM_mapping, f, indent=2)

    print(f"\n已保存:")
    print(f"  原始XML: {raw_xml_path}")
    print(f"  SoM映射: {som_mapping_path}")
    print(f"  标记图片: {screenshot_file_info.get_screenshot_fullpath()}")

    # 示例：显示前5个标记
    print(f"\n前5个SoM标记:")
    for mark_id in list(perception_infos.SoM_mapping.keys())[:5]:
        coords = perception_infos.convert_marks_to_coordinates(mark_id)
        print(f"  标记{mark_id}: {coords}")


if __name__ == "__main__":
    asyncio.run(main())
