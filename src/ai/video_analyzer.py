from pathlib import Path
from typing import Dict, List, Optional

from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

from ..logger import logger


class VideoAnalyzer:
    """视频文件分析器，使用hachoir-metadata获取视频时长等信息"""

    @staticmethod
    def get_video_duration(file_path: Path) -> Optional[float]:
        """
        获取视频文件时长（分钟）

        Args:
            file_path: 视频文件路径

        Returns:
            视频时长（分钟），失败返回None
        """
        try:
            parser = createParser(str(file_path))
            if not parser:
                logger.warning(f"[视频分析] 无法创建解析器: {file_path.name}")
                return None

            metadata = extractMetadata(parser)
            if not metadata:
                logger.warning(f"[视频分析] 无法提取元数据: {file_path.name}")
                return None

            # 获取时长信息
            duration = metadata.get("duration")
            if duration:
                # hachoir返回的时长是datetime.timedelta对象
                duration_seconds = duration.total_seconds()
                return duration_seconds / 60.0  # 转换为分钟
            else:
                logger.warning(f"[视频分析] 未找到时长信息: {file_path.name}")
                return None

        except Exception as e:
            logger.warning(f"[视频分析] 无法获取 {file_path.name} 的时长: {str(e)}")
            return None
        finally:
            # 确保解析器被正确关闭
            if "parser" in locals() and parser:
                parser.close()

    @staticmethod
    def analyze_video_files(base_path: Path, file_paths: List[Path]) -> List[Dict]:
        """
        分析多个视频文件

        Args:
            base_path: 媒体文件的根目录
            file_paths: 视频文件路径列表

        Returns:
            包含文件信息的字典列表
        """
        results = []

        for file_path in file_paths:
            if not file_path.exists():
                continue

            file_info = {
                "filename": file_path.name,
                "path": str(file_path.relative_to(base_path)),
                "size": file_path.stat().st_size,
                "duration": VideoAnalyzer.get_video_duration(file_path),
            }

            results.append(file_info)

        logger.info(f"[视频分析] 分析了 {len(results)} 个视频文件")
        return results

    @staticmethod
    def get_video_info(file_path: Path) -> Optional[Dict]:
        """
        获取单个视频文件的详细信息

        Args:
            file_path: 视频文件路径

        Returns:
            视频信息字典
        """
        parser = None
        try:
            parser = createParser(str(file_path))
            if not parser:
                logger.error(f"[视频分析] 无法创建解析器: {file_path.name}")
                return None

            metadata = extractMetadata(parser)
            if not metadata:
                logger.error(f"[视频分析] 无法提取元数据: {file_path.name}")
                return None

            info = {
                "filename": file_path.name,
                "path": str(file_path),
                "size": file_path.stat().st_size,
            }

            # 获取时长
            duration = metadata.get("duration")
            if duration:
                info["duration"] = duration.total_seconds() / 60.0  # 转换为分钟

            # 获取比特率
            bit_rate = metadata.get("bit_rate")
            if bit_rate:
                info["bitrate"] = bit_rate

            # 获取视频分辨率
            width = metadata.get("width")
            height = metadata.get("height")
            if width and height:
                info["width"] = width
                info["height"] = height

            # 获取帧率
            frame_rate = metadata.get("frame_rate")
            if frame_rate:
                info["fps"] = float(frame_rate)

            # 获取视频编码
            video_codec = metadata.get("compression")
            if video_codec:
                info["video_codec"] = video_codec

            # 获取音频信息
            audio_codec = metadata.get("audio_codec")
            if audio_codec:
                info["audio_codec"] = audio_codec

            audio_channels = metadata.get("nb_channel")
            if audio_channels:
                info["audio_channels"] = audio_channels

            sample_rate = metadata.get("sample_rate")
            if sample_rate:
                info["sample_rate"] = sample_rate

            return info

        except Exception as e:
            logger.error(f"[视频分析] 获取 {file_path.name} 信息失败: {str(e)}")
            return None
        finally:
            # 确保解析器被正确关闭
            if parser:
                parser.close()
