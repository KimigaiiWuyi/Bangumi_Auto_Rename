IGNORE_DIR = ['cd', 'scan']
IGNORE_SUFFIX = ['.rar', '.zip', '.7z', '.webp', '.jpg', '.png']
EXTRA_TAG = [
    'NCOP',
    'NCED',
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
    'Picture Drama',
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
    # '.mka',   # 一般来说无需单独分析外挂音轨
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
    r' (I{2,3})',
    r' (I{1,3}V)',
    r' (VI{2,3})',
    r'S([\d]{1,2})',
    r'第([\d一二三四五六七八九零]{1,2})(季|部分|部)',
    r'([\d]{1,2})nd Season',
    r'Season ([\d]{1,2})',
    r' ([\d]{1,2})',
    r'(First|Second|Third|Fourth|Fifth) Season',
]
episode_partten = [
    r'[Ee]([\d]{1,2})',
    r'第([\d一二三四五六七八九零]{1,2})话',
    r'([\d]{1,2})[Ee]pisode',
    r'([\d]{1,2})[Ee]ps',
    r'\[(\d{1,2})\]',
]
NUM_MAP = {
    'First': 1,
    'Second': 2,
    'Third': 3,
    'Fourth': 4,
    'Fifth': 5,
}
ROMA_MAP = {
    'II': 2,
    'III': 3,
    'IV': 4,
    'V': 5,
    'VI': 6,
    'VII': 7,
}
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
