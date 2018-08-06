SAKUGABOORU_BASE_URL = "https://www.sakugabooru.com/"
SAKUGABOORU_DATA_URL = SAKUGABOORU_BASE_URL + "data/"
SAKUGABOORU_PREVIEW_URL = SAKUGABOORU_DATA_URL + "preview/"
SAKUGABOORU_PREVIEW_EXT = "jpg"
SAKUGABOORU_POST = SAKUGABOORU_BASE_URL + "post/show/"

PLAIN_MEDIA_EXTS = ('jpg', 'jpeg', 'png')
ANIMATED_MEDIA_EXTS = ('gif', 'mp4', 'webm')

SAKUGABOORU_MEDIA_DIR = "sakugabooru"
WEIBO_MEDIA_DIR = "weibo"

PALETTE_FILE_NAME = "palette.png"

ANN_URL = "http://www.animenewsnetwork.com/"
ANN_SEARCH_ENDPOINT = "encyclopedia/search/name"
ANN_PEOPLE_ENDPOINT = "encyclopedia/people.php"

MAL_URL = "https://myanimelist.net/"
MAL_SEARCH_ENDPOINT = "anime.php"
MAL_ANIME_ENDPOINT = "anime/"

BANGUMI_API_URL = "https://api.bgm.tv/"
BANGUMI_SEARCH_ENDPOINT = "search/subject/"
BANGUMI_SUBJECT_ENDPOINT = "subject/"

GOOGLE_KGS_URL = "https://kgsearch.googleapis.com/"
GOOGLE_KGS_SEARCH_ENDPOINT = "v1/entities:search"
GOOGLE_KGS_ENTITY_URI = "http://g.co/kg/"

ATWIKI_SEARCH_URI = "https://atwiki.jp/wiki/"
SAKUGAWIKI_URL_PATTERN = r'(?<=atwiki\.jp/sakuga/pages/)\d*(?=\.html)'
ANIMEWIKI_URL_PATTERN = r'(?<=atwiki\.jp/anime_wiki/pages/)\d*(?=\.html)'

ASDB_SEARCH_URI = 'http://seesaawiki.jp/w/radioi_34/search?search_target=page_name&keywords='

SYNONYM_DICT = {
    'ō': 'o',
    'Ō': 'O',
    '！': '!',
    'ū': 'u'
}
