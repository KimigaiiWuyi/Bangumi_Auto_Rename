import re
import difflib
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from ..logger import logger
from .utils import (
    NUM_MAP,
    ROMA_MAP,
    cn_num,
    keywords,
    code_partten,
    season_partten,
    episode_partten,
    bracket_patterns,
)


def _clean_title_case_insensitive(title: str):
    # 将关键词和标题转换为小写进行匹配
    lower_keywords = [kw.lower() for kw in keywords]
    j = '|'.join(re.escape(kw) for kw in lower_keywords)
    keyword_regex = re.compile(j)
    remain_count=0
    # 查找所有匹配的括号内容
    matches=re.findall('|'.join(bracket_patterns),title)
    for match in matches:
        # 转为小写进行匹配
        if keyword_regex.search(match.lower()):
            title = title.replace(match, '')
        else:
            remain_count+=1
    # 如果有超过一个括号，则放弃，转而使用remove_tag skip=True的方案
    if remain_count>1:
        return ""
    # 返回清理后的标题
    return title.strip()[1:-1]



def chinese_to_number(chinese_numeral):
    chinese_digits = {
        '零': 0,
        '一': 1,
        '二': 2,
        '三': 3,
        '四': 4,
        '五': 5,
        '六': 6,
        '七': 7,
        '八': 8,
        '九': 9,
    }
    if chinese_numeral in chinese_digits:
        return chinese_digits[chinese_numeral]
    return None


def remove_tag(title: str, skip=False):
    '''
    该步骤将带括号的文件名中，包含【指定关键词】的【任意括号】内容删除。

    [LoliHouse] Shangri / 香格里拉 [WebRip 1080p HEVC-10bit AAC]【简繁内封字幕】

    将会变为

    Shangri / 香格里拉

    如果指定`skip=True`，则会保留第二个匹配的括号，将会变为

    Shangri / 香格里拉 [WebRip 1080p HEVC-10bit AAC]

    当指定文件夹名字是下面类型的，会很有用

    [LoliHouse] [Shangri / 香格里拉] [WebRip 1080p HEVC-10bit AAC]【简繁内封字幕】
    '''
    s = title
    if skip:
        # 创建一个字典来追踪每种括号的匹配次数
        counts = {pattern: 0 for pattern in bracket_patterns}

        # 定义替换函数，追踪匹配次数并决定是否保留第二个匹配
        def replace_match(pattern, match):
            counts[pattern] += 1
            # 保留每种括号的第二个匹配，否则去除
            if counts[pattern] == 2:
                return match.group(0)
            else:
                return ''

        # 对每个模式应用相应的匹配逻辑
        for pattern in bracket_patterns:
            s = re.sub(pattern, lambda m: replace_match(pattern, m), s)
    else:
        # 不启用跳过规则，正常删除所有匹配项
        for pattern in bracket_patterns:
            s = re.sub(pattern, '', s)

    remove_tag_s = s.strip()
    logger.info(f'[移除标签工具] {remove_tag_s}')
    if not remove_tag_s:
        s = _clean_title_case_insensitive(title)

    return s.strip()


def divide_by_year(filename: str) -> Tuple[str, int]:
    '''
    该步骤将文件名中，按照年份分割，并提取年份前面的内容。

    Shangri / 香格里拉.2022

    将会变为

    Shangri / 香格里拉.
    '''
    match = re.findall(r'\d+', filename)
    for i in match:
        if 2035 >= float(i) >= 1901:
            name = filename.split(i)
            return name[0], int(i)
    else:
        return filename, 0


def remove_season(s: str):
    '''
    该步骤将文件名中, 类似季度的内容剔除

    Shangri / 香格里拉.S01E01

    将会变为

    Shangri / 香格里拉.E01
    '''
    for p in season_partten:
        s = re.sub(p, '', s)
    return s.strip()


def remove_episode(s: str):
    '''
    该步骤将文件名中, 类似剧集的内容剔除
    Shangri / 香格里拉.E01
    将会变为
    Shangri / 香格里拉.
    '''
    for p in episode_partten:
        s = re.sub(p, '', s)
    return s.strip()


def is_chinese_percentage_sufficient(text: str):
    '''
    用于判断字符串中 中文字符的比例是否至少占 25%
    '''
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    chinese_chars = chinese_pattern.findall(text)
    total_chars = len(text)
    chinese_char_count = len(chinese_chars)
    if total_chars > 0:
        return chinese_char_count / total_chars >= 0.25
    else:
        return False


def extract_season(text: str):
    '''
    用于提取字符串中的 季 信息
    '''

    # 匹配 第1季, 第二季 等
    match = re.search(r'第([\d一二三四五六七八九零]{1,2})(季|部分|部)', text)
    if match:
        season_str = match.group(1)
        if season_str.isdigit():
            return int(season_str)
        else:
            # 中文数字转换为阿拉伯数字
            season_number = 0
            for char in season_str:
                _a = chinese_to_number(char)
                if _a is not None:
                    season_number += _a
            return season_number

    for p in season_partten:
        match = re.search(p, text)
        if match:
            if p == r'(First|Second|Third|Fourth|Fifth) Season':
                return NUM_MAP.get(match.group(1), 1)
            elif p == r'第([\d一二三四五六七八九零]{1,2})(季|部分|部)':
                continue
            elif p == r' (I{2,3})' or p == r' (I{1,3}V)' or p == r' (VI{2,3})':
                return ROMA_MAP.get(match.group(1), 1)
            else:
                if match:
                    return int(match.group(1))

    # 未找到匹配项
    return -1


def find_common_substrings_in_all(
    filenames: List[str], min_length: int = 3
) -> List[str]:
    common_substrings: List[str] = []

    # 取第一个文件名作为初始比较基础
    base_string = filenames[0]

    for filename in filenames[1:]:
        matcher = difflib.SequenceMatcher(None, base_string, filename)
        blocks = matcher.get_matching_blocks()

        # 每次匹配相似块，保留长度大于min_length的部分
        for match in blocks:
            if match.size > min_length:
                A = match.a
                B = match.size
                substring = base_string[A : A + B]  # noqa: E203
                if substring not in common_substrings:
                    common_substrings.append(substring)

    # 只保留在所有文件中都存在的相似部分
    final_common_substrings: List[str] = []
    for substring in common_substrings:
        if all(substring in filename for filename in filenames):
            final_common_substrings.append(substring)

    logger.debug(f'【相似部分】：{final_common_substrings}')
    return final_common_substrings


def find_unique_parts_in_videos(directory: Path):
    '''
    用于提取某个路径中所有文件的公共相似部分
    '''

    video_ext = ['.mp4', '.mkv', '.avi', '.mov', '.flv']
    files: List[Path] = [
        file for file in directory.iterdir() if file.suffix in video_ext
    ]
    filenames: List[str] = [file.stem for file in files]

    if len(filenames) < 2:
        return None

    # 找出所有文件的公共相似部分
    common_parts = find_common_substrings_in_all(filenames)

    return common_parts


def remove_similar_part(common_parts: List[str], filename: str):
    for common_part in common_parts:
        if len(common_part) > 3:  # 确保只移除长度大于3的部分
            pattern = re.escape(common_part)
            filename = re.sub(pattern, '', filename).strip()
    logger.debug(f'【移除相似部分】：{filename}')
    return filename


def remove_code(s: str) -> str:
    for p in code_partten:
        s = re.sub(p, '', s)
    return s


def extract_base_num(filename: str) -> Optional[float]:
    match = re.search(r'S\d+E(\d+)', filename)
    if match:
        return float(match.group(1))
    else:
        return None


def match_and_extract(input_string: str):
    '''
    用于提取字符串中的 季和集 信息
    S01E01
    '''

    pattern = re.compile(r'S(\d+)E(\d+)')
    match = pattern.search(input_string)

    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
        return season, episode
    else:
        return None


def extract_number(filename: str) -> Optional[float]:
    match = re.search(
        r'(\d+\.?\d+|[零一二三四五六七八九十百千万]+\.?[\.零一二三四五六七八九十百千万]+)',
        filename,
    )
    if match:
        r = match.group(1)
        if r.isdigit():
            return int(r)
        else:
            return chinese_to_arabic(r)
    else:
        return None


def to_sim_max(all_similaritys: List[Dict[float, int]]):
    max_key = float('-inf')
    max_value = 1
    for similaritys in all_similaritys:
        _max_key = float('-inf')
        _max_value = 1

        for key, value in similaritys.items():
            if key > _max_key:
                _max_key = key
                _max_value = value

        if _max_key > max_key:
            max_key = _max_key
            max_value = _max_value

    if max_key > 0.6:
        season_id = max_value
    else:
        season_id = 1

    return season_id


def chinese_to_arabic(cn: str) -> int:
    unit = 0
    ldig = []

    for cndig in reversed(cn):
        if cndig in cn_num:
            num = cn_num[cndig]
            if num == 10 or num == 100 or num == 1000 or num == 10000:
                if num > unit:
                    unit = num
                    if unit == 10000:
                        ldig.append(unit)
                        unit = 1
                else:
                    unit *= num
            else:
                if unit:
                    num *= unit
                    unit = 0
                ldig.append(num)
    if unit == 10:  # 处理个位为0的情况，如 '十'
        ldig.append(10)

    val, tmp = 0, 0
    for x in reversed(ldig):
        if x == 10000:
            val += tmp * x
            tmp = 0
        else:
            tmp += x
    val += tmp
    return val
