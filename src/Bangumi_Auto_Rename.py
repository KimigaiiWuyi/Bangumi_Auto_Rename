import tmdbsimple as tmdb
import re
import argparse
from pathlib import Path
from typing import List, Dict, Optional
import shutil
import datetime
import json
from time import sleep
import os
from difflib import SequenceMatcher
from jikanpy import Jikan
import difflib

jikan = Jikan()


IGNORE_DIR = ['cd', 'scan']
IGNORE_SUFFIX = ['.rar', '.zip', '.7z', '.webp', '.jpg', '.png']
EXTRA_TAG = [
    'Menu',
    'Teaser',
    'IV',
    'CM',
    'NC',
    'OP',
    'PV',
    'ED',
    'Advice',
    'Trailer',
    'Event',
    'Fans',
    '访谈',
    'Preview',
    '预告',
    '特典',
    '映像',
]
S0_TAG = [
    r'OVA',
    r'OVA',
    r'OAD',
    r'Special',
    r'sp',
    r'SP',
    r'00',
    r'\.5',
    r'Chaos no Kakera',
]
VIDEO_SUFFIX = [
    '.mp4',
    '.mka',
    '.mkv',
    '.avi',
    '.wmv',
    '.flv',
    '.mov',
    '.mpg',
    '.mpeg',
    '.m4v',
    '.rm',
    '.rmvb',
]

keywords = [
    '01',
    '1080P',
    'FLAC',
    '简繁',
    '外挂',
    'MKV',
    'MP4',
    'TV',
    '全集',
    'HEVC',
    '8bit',
    '10bit',
    '720P',
    '2160P',
    '4K',
    'BD',
    'RIP',
    'DBD-raws',
]

bracket_patterns = [
    r'\[.*?\]',
    r'【.*?】',
    r'《.*?》',
    r'<.*?>',
    r'\(.*?\)',
    r'（.*?）',
]
cn_num = {
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
    '十': 10,
    '百': 100,
    '千': 1000,
    '万': 10000,
}
season_partten = [
    r'S([\d]{1,2})',
    r'第([\d一二三四五六七八九零]{1,2})(季|部分|部)',
    r'([\d]{1,2})nd Season',
    r'Season ([\d]{1,2})',
]
code_partten = [
    r'Ma[\d]{1,2}[pP]',
    r'[\d]{3,4}[pP]',
    r'x264|x265',
    r'_flac',
    r'x265',
    r'h264',
    r'h265',
    r'10bit',
    r'8bit',
]

# 前景色
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

# 背景色
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"
BG_CYAN = "\033[46m"
BG_WHITE = "\033[47m"

# 样式
RESET = "\033[0m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"


def clean_title_case_insensitive(title: str):
    # 将关键词和标题转换为小写进行匹配
    lower_keywords = [kw.lower() for kw in keywords]
    j = '|'.join(re.escape(kw) for kw in lower_keywords)
    keyword_regex = re.compile(j)

    # 遍历所有括号类型
    for pattern in bracket_patterns:
        # 查找所有匹配的括号内容
        matches = re.findall(pattern, title)  # 保留原始大小写内容
        for match in matches:
            # 转为小写进行匹配
            if keyword_regex.search(match.lower()):
                title = title.replace(match, '')  # 删除原始大小写内容

    # 返回清理后的标题
    return title.strip()[1:-1]


def remove_similar_part(common_parts: List[str], filename: str):
    for common_part in common_parts:
        if len(common_part) > 3:  # 确保只移除长度大于3的部分
            pattern = re.escape(common_part)
            filename = re.sub(pattern, '', filename).strip()
    print(f'【移除相似部分】：{filename}')
    return filename


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

    print(f'【相似部分】：{final_common_substrings}')
    return final_common_substrings


# 遍历路径并筛选出视频文件
def find_unique_parts_in_videos(
    directory: Path,
):
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


def match_and_extract(input_string: str):
    pattern = re.compile(r'S(\d+)E(\d+)')
    match = pattern.search(input_string)

    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
        return season, episode
    else:
        return None


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


def extract_season(text: str):
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
        if p != r'第([\d一二三四五六七八九零]{1,2})(季|部分|部)':
            match = re.search(p, text)
            if match:
                return int(match.group(1))

    # 未找到匹配项
    return 1


def remove_season(s: str):
    for p in season_partten:
        s = re.sub(p, '', s)
    return s.strip()


def remove_code(s: str) -> str:
    for p in code_partten:
        s = re.sub(p, '', s)
    return s


def remove_tag(title: str, skip=False):
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
    print(f'【移除标签】：{remove_tag_s}')
    if not remove_tag_s:
        s = clean_title_case_insensitive(title)

    return s.strip()


def extra_tag(s: str):
    combined_results = []
    for pattern in bracket_patterns:
        matches = re.findall(pattern, s)
        combined_results.extend(matches)
    return ''.join(combined_results)


def divide_by_year(filename: str) -> str:
    match = re.findall(r'\d+', filename)
    for i in match:
        if float(i) >= 1901:
            name = filename.split(i)
            return name[0]
    else:
        return filename


def extract_base_num(filename: str) -> Optional[float]:
    match = re.search(r'S\d+E(\d+)', filename)
    if match:
        return float(match.group(1))
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


def is_chinese_percentage_sufficient(text: str):
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    chinese_chars = chinese_pattern.findall(text)
    total_chars = len(text)
    chinese_char_count = len(chinese_chars)
    if total_chars > 0:
        return chinese_char_count / total_chars >= 0.25
    else:
        return False


def get_tv_info(query: str):
    if ' III' in query:
        query = query.replace(' III', '')
    elif ' II' in query:
        query = query.replace(' II', '')

    for i in range(3):
        try:
            for _ in range(2):
                search = tmdb.Search()
                query = remove_season(remove_tag(query).strip('!'))
                print(f'【TMDB搜索】：{query}')
                search.tv(
                    query=query,
                    language='zh-CN',
                )
                target_list = search.__dict__['results']
                if target_list:
                    target = target_list[0]
                    name = target['name']
                    tv = tmdb.TV(target['id'])
                    tv.info()
                    print(tv.__dict__)
                    return name, tv.__dict__
                else:
                    if is_chinese_percentage_sufficient(query):
                        query = re.sub(r'[a-zA-Z]', '', query)
            return '', None
        except:  # noqa:E722, B001
            sleep(5)
            print(f'网络错误, 重试第{i + 1}次中...')
    return '', None


def get_moive_info(query: str):
    for i in range(3):
        try:
            search = tmdb.Search()
            search.movie(
                query=remove_season(remove_tag(query).strip('!')),
                language='zh-CN',
            )
            target_list = search.__dict__['results']
            if target_list:
                target = target_list[0]
                name = target['title']
                movie = tmdb.Movies(target['id'])
                movie.info()
                print(movie.__dict__)
                return name, movie.__dict__
            return '', None
        except:  # noqa:E722, B001
            sleep(5)
            print(f'网络错误, 重试第{i + 1}次中...')
    return '', None


def get_tv_season_info(tv: Dict) -> List[Dict]:
    return tv['seasons']


def process_sub(
    itme_path_main_name: str,
    item_repeat: Optional[List[str]],
    item_path: Path,
    work_path: Path,
    R: Dict[Path, Path],
    season_id: int,
):
    item_name = item_path.name
    if item_repeat:
        item_name_remove = remove_similar_part(item_repeat, item_path.stem)
    else:
        item_name_remove = item_path.stem

    item_name_l = item_name_remove.lower()
    item_suffix = item_path.suffix.lower()

    n_item_name_l = item_name.replace(itme_path_main_name, '').lower()
    print(f'移去主要内容后的文件名Lower：{n_item_name_l}')

    for ignore_dir in IGNORE_DIR:
        if ignore_dir in item_path.name:
            print(f'忽略文件夹：{item_path.name}')
            break
    else:
        for ignore_tag in IGNORE_SUFFIX:
            if ignore_tag in item_suffix:
                print(f'忽略文件：{item_path.name}')
                break
        else:
            for ex in EXTRA_TAG:
                if re.search(rf'{ex.lower()}', n_item_name_l):
                    t = work_path / 'extra'
                    R[item_path] = t / item_name
                    break
            else:
                for s0 in S0_TAG:
                    if re.search(rf'{s0.lower()}[\d]{{0,3}}', item_name_l):
                        t = work_path / 'Season0'
                        R[item_path] = t / item_name
                        break
                else:
                    _item_name = remove_code(remove_season(item_name))
                    epp = extract_base_num(_item_name)
                    if epp is None:
                        ep = extract_number(_item_name)
                    else:
                        ep = int(epp)
                    if ep is None:
                        season_id = 0
                        ep = 0
                    else:
                        ep = int(ep)

                    _idata = match_and_extract(item_name)
                    if _idata:
                        season_id, ep = _idata[0], _idata[1]

                    t = work_path / f'Season{season_id}'

                    ep = f'0{ep}' if ep < 10 else ep
                    s = f'0{int(season_id)}'
                    ss = s if season_id < 10 else int(season_id)
                    t.mkdir(parents=True, exist_ok=True)
                    ft = f'S{ss}E{ep}'
                    R[item_path] = t / f'{ft} - {item_name}'


# 这是用于处理路径内已经是视频文件的，例如直接就是Season1或者子文件夹的情况
def process_path(path: Path, R: Dict[Path, Path]):
    '''
    if not path.is_dir():
        return
    '''
    # 允许处理单独视频情况
    rtpath_name = remove_tag(path.name)
    if not rtpath_name:
        rtpath_name = remove_tag(path.name, True)
    path_atri = re.split(r'[\s-]+', rtpath_name)
    if len(path_atri) > 3:
        # path_atri.pop(0)
        rtpath_name = ' '.join(path_atri)
    if rtpath_name.count('.') >= 3:
        rtpath_name = ' '.join(rtpath_name.split('.'))
        rtpath_name = divide_by_year(rtpath_name)
        rtpath_name = remove_season(rtpath_name)

    print(f'【处理路径】：{path.name}')
    print(f'【去除TAG】：{rtpath_name}')
    if path.is_file() and path.suffix.lower() not in VIDEO_SUFFIX:
        return

    if (
        path.is_dir() and len([i for i in path.iterdir() if i.is_file()]) <= 6
    ) or path.is_file():
        name, moive_info = get_moive_info(rtpath_name)
        print(f'电影名称: {name}')
        if IS_ANIME:
            _WORK_PATH = ANIME_MOVIE_PATH
        else:
            _WORK_PATH = MOVIE_PATH

        if not name:
            print(
                f'{BG_YELLOW}【警告】【警告】无法识别，跳过{rtpath_name}【警告】【警告】{RESET}'
            )
        if moive_info:
            first_data = moive_info['release_date']
            first_year = first_data.split('-')[0]
            work_path = _WORK_PATH / f'{name} ({first_year})'
            work_path.mkdir(parents=True, exist_ok=True)
            if path.is_file():
                R[path] = work_path / f'{name} - {path.name}'
            else:
                for item_path in path.iterdir():
                    item_name = item_path.name
                    R[item_path] = work_path / f'{name} - {item_name}'
    else:
        name, tv_info = get_tv_info(rtpath_name)
        print(f'剧集名称: {name}')
        if IS_ANIME:
            if not name:
                print('【TMDB未搜索到】转为MyAnimeList搜索！')
                search_result = jikan.search(
                    'anime',
                    rtpath_name,
                    page=1,
                )
                for i in search_result['data']:
                    if i['type'] == 'Anime':
                        data = i
                        break
                else:
                    for i in search_result['data']:
                        if i['type'] == 'TV':
                            data = i
                            break
                    else:
                        data = search_result['data'][0]
                titles = data['titles']
                print(f'【MyAnimeList】【识别结果】: {titles}')
            else:
                titles = None
            _WORK_PATH = ANIME_PATH
        else:
            titles = [{'type': 'Default', 'title': name}]
            _WORK_PATH = BANGUMI_PATH

        if titles:
            for title in titles:
                if title['type'] == 'Japanese':
                    name, tv_info = get_tv_info(title['title'])
                    print(
                        f'【TMDB】【优先日文搜索】【{title["type"]}】剧集名称: {name}'
                    )
                    if name:
                        break
            else:
                for title in titles:
                    name, tv_info = get_tv_info(title['title'])
                    print(f'【TMDB】【{title["type"]}】剧集名称: {name}')
                    if name:
                        break
        if not name:
            print(
                f'{BG_YELLOW}【警告】【警告】无法识别，跳过{rtpath_name}【警告】【警告】{RESET}'
            )

        if tv_info:
            first_data: str = tv_info['first_air_date']
            first_year = first_data.split('-')[0]
            work_path = _WORK_PATH / f'{name} ({first_year})'

            season_id = 1
            all_similaritys: List[Dict] = []

            for season in get_tv_season_info(tv_info):
                season_id = season['season_number']
                target_fold = work_path / f'Season{season_id}'
                target_fold.mkdir(parents=True, exist_ok=True)

                if season_id == 0 or season_id == 1:
                    season_id = 1

                sname: str = season['name']
                print(f'【SNAME】: {sname}')

                if sname.startswith('Season') and re.search(r'\d', sname):
                    int_season = extract_season(sname)
                    print(f'【提取信息季号】:{int_season}')
                    int_rtpath_name = extract_season(path.name)
                    print(f'【提取标题季号】:{int_rtpath_name}')
                    season_id = int_rtpath_name
                    break

                # 如果不是Season1的情况下，sname处于路径之中，则直接跳过
                if not (sname.strip().startswith('Season') and '1' in sname):
                    if sname in path.name:
                        break

                    if not titles:
                        print('【SEASON】【TMDB未搜索到】转为MyAnimeList搜索！')
                        search_result = jikan.search(
                            'anime',
                            rtpath_name,
                            page=1,
                        )
                        for i in search_result['data']:
                            if i['type'] == 'Anime':
                                data = i
                                break
                        else:
                            for i in search_result['data']:
                                if i['type'] == 'TV':
                                    data = i
                                    break
                            else:
                                data = search_result['data'][0]
                        titles = data['titles']
                        print(f'【MyAnimeList】【识别结果】: {titles}')

                    # 或者计算相似度
                    for title in titles:
                        similaritys = {}
                        if title['type'] in [
                            'Default',
                            'Synonym',
                            'English',
                            'French',
                        ]:
                            ename = title['title']
                            # print(f'ENAME: {ename}')
                            similarity = SequenceMatcher(
                                None,
                                sname,
                                remove_tag(ename),
                            ).ratio()

                            # print(f'相似度{tindex}：{similarity}')
                            similaritys[similarity] = season_id
                        all_similaritys.append(similaritys)
            else:
                if all_similaritys:
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

                    if max_key > 0.5:
                        season_id = max_value
                    else:
                        season_id = 1

            print(f'季号：{season_id}')

            print(path)
            repeat = find_unique_parts_in_videos(path)
            itme_name = remove_tag(rtpath_name).strip('!')
            for item_path in path.iterdir():
                if item_path.is_dir():
                    repeat = find_unique_parts_in_videos(item_path)
                    for sub_item in item_path.iterdir():
                        process_sub(
                            itme_name,
                            repeat,
                            sub_item,
                            work_path,
                            R,
                            season_id,
                        )
                else:
                    process_sub(
                        itme_name,
                        repeat,
                        item_path,
                        work_path,
                        R,
                        season_id,
                    )

    trans_file(R)
    R.clear()


def trans_file(R: Dict[Path, Path]):
    # 用json备份一下R文件
    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d-%H")
    _input = INPUT_PATH if INPUT_PATH.is_dir() else INPUT_PATH.parent
    path = _input / f'R-{now_str}.json'

    _R = {str(k): str(v) for k, v in R.items()}

    if path.exists():
        with open(str(path), 'r', encoding='utf-8') as f:
            R_old: Dict = json.load(f)
        _R.update(R_old)

    with open(str(path), 'w', encoding='utf-8') as f:
        json.dump(_R, f, ensure_ascii=False)

    for source_path, target_path in R.items():
        try:
            if target_path.is_dir() or source_path.is_dir():
                continue
            if not target_path.parent.exists():
                target_path.parent.mkdir(parents=True)
            if PROCESS == 'MOVE':
                shutil.move(source_path, target_path)
            elif PROCESS == 'COPY':
                shutil.copy(source_path, target_path)
            elif PROCESS == 'LINK':
                try:
                    os.link(source_path, target_path)
                except:  # noqa:E722
                    print(f'{BG_YELLOW}无法创建硬链接, 尝试软链接...{RESET}')
                    os.symlink(source_path, target_path)
            else:
                print('PROCESS模式错误！')
        except Exception as e:
            print(e)
            print('遇到错误, 移动失败, 跳过...')
            continue


def revert(path: str):
    # 载入R文件，反向复制其中对应路径
    with open(path, 'r', encoding='utf-8') as f:
        _R: Dict = json.load(f)

    R = {Path(k): Path(v) for k, v in _R.items()}

    for target_path, source_path in R.items():
        try:
            if target_path.is_dir() or source_path.is_dir():
                continue
            if not target_path.parent.exists():
                target_path.parent.mkdir(parents=True)
            if PROCESS == 'MOVE':
                shutil.move(source_path, target_path)
            elif PROCESS == 'COPY':
                shutil.copy(source_path, target_path)
            elif PROCESS == 'LINK':
                print('模式为硬链接, 无需操作...')
            else:
                print('PROCESS模式错误！')
        except Exception as e:
            print(e)
            print('遇到错误, 移动失败, 跳过...')
            continue


def process_task_path(path: Path, R: Dict):
    if path.is_dir():
        is_video = False
        for sub_path in path.iterdir():
            if not sub_path.is_dir() and sub_path.suffix in VIDEO_SUFFIX:
                is_video = True

        if is_video:
            process_path(path, R)
        else:
            for sub_path in path.iterdir():
                process_path(sub_path, R)
    else:
        process_path(path, R)


def process():
    # 进入主目录
    for path in INPUT_PATH.iterdir():
        if path.is_dir():
            process_task_path(path, {})


parser = argparse.ArgumentParser(
    description="为动漫番剧集合自动格式化文件结构和名称, 方便Emby刮削!"
)

parser.add_argument(
    "--w",
    type=str,
    help="工作模式: ALL/TASK",
    default="TASK",
    required=True,
)
parser.add_argument(
    "--p",
    type=str,
    help="处理模式: MOVE/COPY/LINK",
    default="LINK",
    required=True,
)
parser.add_argument(
    "--t",
    type=str,
    help="是否为动画类型",
    default='yes',
    required=True,
)
parser.add_argument(
    "--k",
    type=str,
    help="TMDB_Key, 需要申请",
    required=True,
)
parser.add_argument(
    "--i",
    type=str,
    help="输入路径",
    required=True,
)
parser.add_argument(
    "--o_anime",
    type=str,
    help="动漫解析完成之后输出路径",
    required=True,
)
parser.add_argument(
    "--o_movie",
    type=str,
    help="电影解析完成之后输出路径",
    required=True,
)
parser.add_argument(
    "--o_anime_movie",
    type=str,
    help="动漫剧场版解析完成之后输出路径",
    required=True,
)
parser.add_argument(
    "--o_bangumi",
    type=str,
    help="剧集解析完成之后输出路径",
    required=True,
)

args = parser.parse_args()
INPUT_PATH = Path(args.i)
PROCESS = args.p
IS_ANIME = (
    False
    if args.t.lower()
    in [
        'false',
        'no',
        'none',
        'null',
        'real',
    ]
    else True
)
ANIME_PATH = Path(rf'{args.o_anime}')
MOVIE_PATH = Path(rf'{args.o_movie}')
ANIME_MOVIE_PATH = Path(rf'{args.o_anime_movie}')
BANGUMI_PATH = Path(rf'{args.o_bangumi}')
tmdb.API_KEY = args.k

ANIME_MOVIE_PATH.mkdir(parents=True, exist_ok=True)
MOVIE_PATH.mkdir(parents=True, exist_ok=True)
ANIME_PATH.mkdir(parents=True, exist_ok=True)
BANGUMI_PATH.mkdir(parents=True, exist_ok=True)

if args.w == 'ALL':
    process()
else:
    process_task_path(INPUT_PATH, {})

while True:
    input("按下回车键继续...")
    break
