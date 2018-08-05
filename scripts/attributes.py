from hub.models import Attribute, Tag

META_ATTRIBUTES = [
    {
        "code": "name_main",
        "name": "名称",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [c[0] for c in Tag.TYPE_CHOICES],
    },
    {
        "code": "alias",
        "name": "别称",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [c[0] for c in Tag.TYPE_CHOICES],
    },
    {
        "code": "name_zh",
        "name": "中文名称",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [c[0] for c in Tag.TYPE_CHOICES],
    },
    {
        "code": "name_ja",
        "name": "日文名称",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [c[0] for c in Tag.TYPE_CHOICES],
    },
    {
        "code": "wiki_zh",
        "name": "中文维基",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [Tag.ARTIST, Tag.COPYRIGHT, Tag.TERMINOLOGY],
    },
    {
        "code": "wiki_ja",
        "name": "日文维基",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [Tag.ARTIST, Tag.COPYRIGHT, Tag.TERMINOLOGY],
    },
    {
        "code": "wiki_en",
        "name": "英文维基",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [Tag.ARTIST, Tag.COPYRIGHT, Tag.TERMINOLOGY],
    },
    {
        "code": "kgs_url",
        "name": "Google Knowledge Graph Search",
        "type": Attribute.STRING,
        "format": None,
        "related_types": [Tag.ARTIST, Tag.COPYRIGHT, Tag.TERMINOLOGY],
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
    },
    {
        "code": "anime_staff_database_link",
        "name": "アニメスタッフデータベース",
        "alias": {
            "en": "Anime Staff Database"
        },
        "type": Attribute.STRING,
        "format": None,
        "related_types": [Tag.COPYRIGHT],
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
    }
]
