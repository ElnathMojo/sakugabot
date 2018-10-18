from hub.models import Attribute, Tag

META_ATTRIBUTES = [
    {
        "code": "name_main",
        "name": "名称",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [c[0] for c in Tag.TYPE_CHOICES],
        "order": 0
    },
    {
        "code": "alias",
        "name": "别称",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [c[0] for c in Tag.TYPE_CHOICES],
        "order": 4
    },
    {
        "code": "name_zh",
        "name": "中文名称",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [c[0] for c in Tag.TYPE_CHOICES],
        "order": 1
    },
    {
        "code": "name_ja",
        "name": "日文名称",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [c[0] for c in Tag.TYPE_CHOICES],
        "order": 2
    },
    {
        "code": "name_en",
        "name": "英文名称",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [c[0] for c in Tag.TYPE_CHOICES],
        "order": 3
    },
    {
        "code": "wiki_zh",
        "name": "中文维基",
        "type": Attribute.STRING,
        "format": None,
        "regex": r"^((https?)://)?zh.wikipedia.org/wiki/[^\s]*$",
        "related_types": [Tag.ARTIST, Tag.COPYRIGHT, Tag.TERMINOLOGY],
        "order": 7
    },
    {
        "code": "wiki_ja",
        "name": "日文维基",
        "type": Attribute.STRING,
        "format": None,
        "regex": r"^((https?)://)?ja.wikipedia.org/wiki/[^\s]*$",
        "related_types": [Tag.ARTIST, Tag.COPYRIGHT, Tag.TERMINOLOGY],
        "order": 7
    },
    {
        "code": "wiki_en",
        "name": "英文维基",
        "type": Attribute.STRING,
        "format": None,
        "regex": r"^((https?)://)?en.wikipedia.org/wiki/[^\s]*$",
        "related_types": [Tag.ARTIST, Tag.COPYRIGHT, Tag.TERMINOLOGY],
        "order": 7
    },
    {
        "code": "kgs_url",
        "name": "Google Knowledge Graph Search",
        "type": Attribute.STRING,
        "format": None,
        "regex": r"^((https?)://)?g.co/kg/g/[^\s]*$",
        "related_types": [Tag.ARTIST, Tag.COPYRIGHT, Tag.TERMINOLOGY],
        "order": 13
    },
    {
        "code": "birth",
        "name": "诞生",
        "alias": {
            "en": "Birth"
        },
        "type": Attribute.DATE,
        "format": None,
        "related_types": [Tag.ARTIST],
        "order": 5
    },
    {
        "code": "bgm_sid",
        "name": "番组计划",
        "alias": {
            "en": "Bangumi"
        },
        "type": Attribute.INTEGER,
        "format": "http://bgm.tv/subject/{}",
        "related_types": [Tag.COPYRIGHT],
        "order": 8
    },
    {
        "code": "ann_pid",
        "name": "动画新闻网",
        "alias": {
            "en": "Anime News Network"
        },
        "type": Attribute.INTEGER,
        "format": "https://www.animenewsnetwork.com/encyclopedia/people.php?id={}",
        "related_types": [Tag.ARTIST],
        "order": 8
    },
    {
        "code": "mal_aid",
        "name": "MyAnimeList",
        "alias": {
            "en": "MyAnimeList"
        },
        "type": Attribute.INTEGER,
        "format": "https://myanimelist.net/anime/{}/",
        "related_types": [Tag.COPYRIGHT],
        "order": 8
    },
    {
        "code": "sakuga_wiki_id",
        "name": "作画@wiki",
        "alias": {
            "en": "Sakuga Wiki"
        },
        "type": Attribute.INTEGER,
        "format": "https://www18.atwiki.jp/sakuga/pages/{}.html",
        "related_types": [Tag.ARTIST, Tag.COPYRIGHT],
        "order": 8
    },
    {
        "code": "anime_wiki_id",
        "name": "アニメ@wiki",
        "alias": {
            "en": "Anime Wiki"
        },
        "type": Attribute.INTEGER,
        "format": "https://www7.atwiki.jp/anime_wiki/pages/{}.html",
        "related_types": [Tag.ARTIST, Tag.COPYRIGHT],
        "order": 8
    },
    {
        "code": "anime_staff_database_link",
        "name": "アニメスタッフデータベース",
        "alias": {
            "en": "Anime Staff Database"
        },
        "type": Attribute.STRING,
        "format": None,
        "regex": r"^((https?)://)?seesaawiki.jp/w/radioi_34/d/[^\s]*$",
        "related_types": [Tag.COPYRIGHT],
        "order": 8
    },
    {
        "code": "twitter_id",
        "name": "推特",
        "alias": {
            "en": "Twitter"
        },
        "type": Attribute.STRING,
        "format": "https://twitter.com/{}",
        "related_types": [Tag.ARTIST, Tag.COPYRIGHT],
        "order": 6
    },
    {
        "code": "blog",
        "name": "博客",
        "alias": {
            "en": "Blog"
        },
        "type": Attribute.STRING,
        "format": None,
        "related_types": [Tag.ARTIST, Tag.COPYRIGHT],
        "order": 6
    },
    {
        "code": "description",
        "name": "简介",
        "alias": {
            "en": "Description"
        },
        "type": Attribute.STRING,
        "format": None,
        "related_types": [c[0] for c in Tag.TYPE_CHOICES],
        "order": 5
    }
]
