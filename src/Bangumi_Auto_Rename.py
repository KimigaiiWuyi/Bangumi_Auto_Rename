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
]
S0_TAG = [
    'OVA01',
    'OVA02',
    'OVA03',
    'OVA04',
    'OVA05',
    'OVA',
    'OAD',
    'Special',
    'sp',
    'SP',
    '00',
    '.5',
    'Chaos no Kakera',
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
ordinal_numbers = {
    "First": 1,
    "Second": 2,
    "Third": 3,
    "Fourth": 4,
    "Fifth": 5,
    " III": 3,
    " II": 2,
    " IV": 4,
}

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


def remove_season(s: str):
    s = re.sub(r'(S\d+)', '', s)
    return s.strip()


def remove_tag(s: str):
    for pattern in bracket_patterns:
        s = re.sub(pattern, '', s)
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


def extract_number(filename: str) -> float:
    match = re.search(
        r'(\d+\.?\d+|[一二三四五六七八九十百千万]+\.?[\.一二三四五六七八九十百千万]+)',
        filename,
    )
    if match:
        r = match.group(1)
        if r.isdigit():
            return int(r)
        else:
            return chinese_to_arabic(r)
    else:
        return 0


def get_tv_info(query: str):
    if ' III' in query:
        query = query.replace(' III', '')
    elif ' II' in query:
        query = query.replace(' II', '')

    for i in range(3):
        try:
            search = tmdb.Search()
            search.tv(
                query=remove_season(remove_tag(query).strip('!')),
                language='zh-CN',
            )
            target_list = search.__dict__['results']
            if target_list:
                target = target_list[0]
                name = target['name']
                tv = tmdb.TV(target['id'])
                tv.info()
                return name, tv.__dict__
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
                return name, movie.__dict__
            return '', None
        except:  # noqa:E722, B001
            sleep(5)
            print(f'网络错误, 重试第{i + 1}次中...')
    return '', None


def get_tv_season_info(tv: Dict) -> List[Dict]:
    return tv['seasons']


def process_sub(
    item_path: Path,
    work_path: Path,
    R: Dict[Path, Path],
    season_id: int,
):
    item_name = item_path.name
    item_name_l = item_name.lower()
    item_name_r = extra_tag(item_name_l)
    item_suffix = item_path.suffix.lower()

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
                if ex.lower() in item_name_r:
                    t = work_path / 'extra'
                    R[item_path] = t / item_name
                    break
            else:
                for s0 in S0_TAG:
                    if s0.lower() in item_name_r:
                        t = work_path / 'Season0'
                        R[item_path] = t / item_name
                        break
                else:
                    t = work_path / f'Season{season_id}'
                    epp = extract_base_num(item_name)
                    if epp is None:
                        ep = int(extract_number(item_name))
                    else:
                        ep = int(epp)
                    ep = f'0{ep}' if ep < 10 else ep
                    s = f'0{int(season_id)}'
                    ss = s if season_id < 10 else int(season_id)
                    t.mkdir(parents=True, exist_ok=True)
                    ft = f'S{ss}E{ep}'
                    R[item_path] = t / f'{ft} - {item_name}'


# 这是用于处理路径内已经是视频文件的，例如直接就是Season1或者子文件夹的情况
def process_path(path: Path, R: Dict[Path, Path]):
    if not path.is_dir():
        return
    rtpath_name = remove_tag(path.name)
    path_atri = re.split(r'[\s-]+', rtpath_name)
    if len(path_atri) > 3:
        path_atri.pop(0)
        rtpath_name = ' '.join(path_atri)
    if rtpath_name.count('.') >= 3:
        rtpath_name = ' '.join(rtpath_name.split('.'))
        rtpath_name = divide_by_year(rtpath_name)

    print(f'【处理路径】：{path.name}')
    print(f'【去除TAG】：{rtpath_name}')
    if len(list(path.iterdir())) <= 9:
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
            first_data: str = moive_info['release_date']
            first_year = first_data.split('-')[0]
            work_path = _WORK_PATH / f'{name} ({first_year})'
            work_path.mkdir(parents=True, exist_ok=True)
            for item_path in path.iterdir():
                item_name = item_path.name
                R[item_path] = work_path / f'{name} - {item_name}'
    else:
        name, tv_info = get_tv_info(rtpath_name)
        print(f'剧集名称: {name}')
        if not name:
            print(
                f'{BG_YELLOW}【警告】【警告】无法识别，跳过{rtpath_name}【警告】【警告】{RESET}'
            )
        if IS_ANIME:
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
                data = search_result['data'][0]
            titles = data['titles']
            _WORK_PATH = ANIME_PATH
        else:
            titles = [{'type': 'Default', 'title': name}]
            _WORK_PATH = BANGUMI_PATH

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
                    is_break = False
                    for oseason in ordinal_numbers:
                        if oseason in rtpath_name:
                            is_break = True
                            season_id = ordinal_numbers[oseason]
                            break
                    if is_break:
                        break

                # 如果不是Season1的情况下，sname处于路径之中，则直接跳过
                if not (sname.strip().startswith('Season') and '1' in sname):
                    if sname in path.name:
                        break

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

            for item_path in path.iterdir():
                if item_path.is_dir():
                    for sub_item in item_path.iterdir():
                        process_sub(sub_item, work_path, R, season_id)
                else:
                    process_sub(item_path, work_path, R, season_id)

    trans_file(R)
    R.clear()


def trans_file(R: Dict[Path, Path]):
    # 用json备份一下R文件
    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d-%H")
    path = INPUT_PATH / f'R-{now_str}.json'

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
    if not args.t
    or args.t.lower()
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
