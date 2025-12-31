"""
应用特定提示加载器

从配置文件中加载针对特定应用的探索提示
"""

from pathlib import Path
from typing import Optional
from .logger import get_logger

logger = get_logger("TipsLoader")


class AppSpecificTipsLoader:
    """应用特定提示加载器"""

    def __init__(self, tips_file: Optional[Path] = None):
        """
        Args:
            tips_file: tips配置文件路径，默认为当前目录下的app_specific_tips.md
        """
        if tips_file is None:
            tips_file = Path(__file__).parent / "app_specific_tips.md"

        self.tips_file = tips_file
        self.tips_content = self._load_tips()

    def _load_tips(self) -> str:
        """加载tips文件内容"""
        try:
            if self.tips_file.exists():
                with open(self.tips_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"成功加载Tips文件: {self.tips_file}")
                return content
            else:
                logger.warning(f"Tips文件不存在: {self.tips_file}")
                return ""
        except Exception as e:
            logger.error(f"加载Tips文件失败: {e}")
            return ""

    def get_tips_for_app(self, app_package: str, app_name: str = "") -> str:
        """获取特定应用的提示

        Args:
            app_package: 应用包名
            app_name: 应用名称（可选）

        Returns:
            格式化后的提示文本
        """
        if not self.tips_content:
            return ""

        # 提取通用提示
        general_tips = self._extract_section(self.tips_content, "## 通用提示")

        # 提取应用特定提示
        app_specific_tips = self._extract_app_section(app_package, app_name)

        # 组合提示
        if app_specific_tips:
            return f"""## ⚠️ 特殊注意事项

### 通用提示
{general_tips}

### 应用特定提示（{app_name or app_package}）
{app_specific_tips}

**请严格遵守上述限制，避免产生真实订单或触发已知问题！**
"""
        else:
            return f"""## ⚠️ 特殊注意事项

{general_tips}

**请严格遵守上述限制，避免产生真实订单或其他不可逆操作！**
"""

    def get_forbidden_items(self, app_package: str, app_name: str = "") -> list:
        """提取严格禁止的操作列表

        Args:
            app_package: 应用包名
            app_name: 应用名称（可选）

        Returns:
            禁止项列表
        """
        if not self.tips_content:
            return []

        # 提取应用特定提示
        app_specific_tips = self._extract_app_section(app_package, app_name)

        if not app_specific_tips:
            return []

        # 查找"严格禁止的操作"部分
        forbidden_items = []
        lines = app_specific_tips.split('\n')
        in_forbidden_section = False

        for line in lines:
            stripped = line.strip()

            # 检测严格禁止section开始
            if '严格禁止' in stripped or '⚠️' in stripped:
                in_forbidden_section = True
                continue

            # 检测section结束（遇到新的子标题）
            if in_forbidden_section and stripped.startswith('####'):
                in_forbidden_section = False
                continue

            # 提取禁止项（以 - 或 • 开头的行）
            if in_forbidden_section and (stripped.startswith('- **不要') or stripped.startswith('- ') or stripped.startswith('• ')):
                # 清理markdown格式
                item = stripped.lstrip('- ').lstrip('• ').replace('**', '').strip()
                if item:
                    forbidden_items.append(item)

        return forbidden_items

    def _extract_section(self, content: str, section_header: str) -> str:
        """提取指定章节的内容

        Args:
            content: 完整内容
            section_header: 章节标题

        Returns:
            章节内容
        """
        lines = content.split('\n')
        section_lines = []
        in_section = False
        section_level = section_header.count('#')

        for line in lines:
            if line.strip().startswith(section_header):
                in_section = True
                continue

            if in_section:
                # 遇到同级或更高级的标题，停止
                if line.strip().startswith('#'):
                    current_level = len(line) - len(line.lstrip('#'))
                    if current_level <= section_level:
                        break

                section_lines.append(line)

        return '\n'.join(section_lines).strip()

    def _extract_app_section(self, app_package: str, app_name: str = "") -> str:
        """提取特定应用的章节

        Args:
            app_package: 应用包名
            app_name: 应用名称

        Returns:
            应用特定的提示内容
        """
        # 查找包含app_package或app_name的章节
        lines = self.tips_content.split('\n')
        app_section_lines = []
        in_app_section = False

        for i, line in enumerate(lines):
            # 查找应用章节标题（包含app_name或app_package）
            if line.strip().startswith('###') and (
                (app_name and app_name in line) or
                (app_package in line)
            ):
                in_app_section = True
                # 不包含标题行本身
                continue

            if in_app_section:
                # 遇到同级标题，停止
                if line.strip().startswith('###'):
                    break
                # 遇到更高级标题，停止
                if line.strip().startswith('##') and not line.strip().startswith('###'):
                    break

                app_section_lines.append(line)

        return '\n'.join(app_section_lines).strip()


# 创建全局实例
_tips_loader = None

def get_tips_loader() -> AppSpecificTipsLoader:
    """获取全局Tips加载器实例"""
    global _tips_loader
    if _tips_loader is None:
        _tips_loader = AppSpecificTipsLoader()
    return _tips_loader
