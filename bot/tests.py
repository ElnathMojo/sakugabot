from django.test import SimpleTestCase, TestCase

from hub.models import Tag
from scripts.init import init_attributes


class TestTasks(TestCase):
    def setUp(self):
        init_attributes()
        Tag.objects.create(name="zetsuen_no_tempest")
        self.maxDiff = None

    def test_auto_task(self):
        from bot.tasks import bot_auto_task
        bot_auto_task()
        from hub.models import Post
        self.assertGreater(len(Post.objects.all()), 0)
        from hub.models import Node
        self.assertGreater(len(Node.objects.all()), 0)

    def test_update_tag_info(self):
        from bot.tasks import update_tags_info_task
        update_tags_info_task(Tag.objects.get(name="zetsuen_no_tempest").pk, update_tag_type=True)
        tag = Tag.objects.get(name="zetsuen_no_tempest")
        tag.refresh_from_db()
        self.assertEqual(tag.type, tag.COPYRIGHT)
        self.assertDictEqual(tag._detail,
                             {
                                 "mal_aid": 14075,
                                 "name_en": "Zetsuen no Tempest",
                                 "name_ja": "絶園のテンペスト",
                                 "bgm_sid": 39794,
                                 "name_zh": "绝园的暴风雨",
                                 "description": "《絕園的暴風雨》是由城平京、左有秀、彩崎廉創作的日本漫畫作品。2009年8月號於『月刊少年GANGAN』"
                                                "上開始連載。本作包含奇幻漫畫、推理漫畫的要素。2012年10月電視動畫開始播放，漫畫本篇與動畫差不多"
                                                "同時期結束。",
                                 "kgs_url": "http://g.co/kg/m/0k8f8qc",
                                 "wiki_zh": "https://zh.wikipedia.org/zh-tw/%E7%B5%95%E5%9C%92%E7%9A%84%E6%9A%B4%E9%A2%A8%E9%9B%A8",
                                 "wiki_ja": "https://ja.wikipedia.org/wiki/%E7%B5%B6%E5%9C%92%E3%81%AE%E3%83%86%E3%83%B3%E3%83%9A%E3%8"
                                            "2%B9%E3%83%88",
                                 "wiki_en": "https://en.wikipedia.org/wiki/Blast_of_Tempest",
                                 "anime_wiki_id": 10622,
                                 "anime_staff_database_link": "http://seesaawiki.jp/w/radioi_34/d/%c0%e4%b1%e0%a4%ce%a5%c6%a5%f3%a5%da%a"
                                                              "5%b9%a5%c8"
                             })


class TestInfoServices(SimpleTestCase):

    def test_ann(self):
        from bot.services.info_service import ANNArtistInfoService
        self.assertDictEqual(ANNArtistInfoService().get_info("yuuko sera"),
                             {'name_ja': '世良悠子', 'ann_pid': 61765, 'name_en': 'Yuuko Sera'})

    def test_mal(self):
        from bot.services.info_service import MALCopyrightInfoService
        self.assertDictEqual(MALCopyrightInfoService().get_info("zenki"),
                             {'mal_aid': 1573, 'name_ja': '鬼神童子ZENKI', 'name_en': 'Kishin Douji Zenki'})

    def test_bgm(self):
        from bot.services.info_service import BangumiCopyrightInfoService
        self.assertDictEqual(BangumiCopyrightInfoService().get_info("Violet Evergarden",
                                                                "紫罗兰永恒花园(ヴァイオレット・エヴァーガーデン)"),
                             {'name_ja': 'ヴァイオレット・エヴァーガーデン', 'bgm_sid': 183878, 'name_zh': '紫罗兰永恒花园',
                          'description': '某个大陆的、某个时代。\r\n大陆南北分割的战争结束了，世界逐渐走向了和平。\r\n在战争中、'
                                         '作为军人而战斗的薇尔莉特·伊芙加登离开了军队，来到了大港口城市。怀抱着战场上一个对她而言'
                                         '比谁都重要的人告诉了她“某个话语”――。\r\n街道上人群踊跃，有轨电车在排列着煤气灯的马路上'
                                         '穿梭着。薇尔莉特在街道上找到了“代写书信”的工作。那是根据委托人的想法来组织出相应语言的工'
                                         '作。\r\n她直面着委托人、触碰着委托人内心深处的坦率感情。与此同时，薇尔莉特在记录书信时，'
                                         '那一天所告知的那句话的意思也逐渐接近了。'})

    def test_atwiki(self):
        from bot.services.info_service import AtwikiInfoService
        self.assertDictEqual(AtwikiInfoService().get_info('高瀬健一', ), {'anime_wiki_id': '257', 'sakuga_wiki_id': '1203'})

    def test_asdb(self):
        from bot.services.info_service import ASDBCopyrightInfoService
        self.assertDictEqual(ASDBCopyrightInfoService().get_info('賭ケグルイ', ), {
            'anime_staff_database_link': 'http://seesaawiki.jp/w/radioi_34/d/%c5%d2%a5%b1%a5%b0%a5%eb%a5%a4',
            'name_ja': '賭ケグルイ'})

    def test_google(self):
        from bot.services.info_service import GoogleKGSArtistInfoService
        self.assertDictEqual(GoogleKGSArtistInfoService().get_info('yuki hayashi'),
                             {'kgs_url': 'http://g.co/kg/g/121wymf_',
                          'description': '林 祐己は、日本のアニメーター、キャラクターデザイナー。東映アニメーション所属。',
                          'name_ja': '林祐己',
                          'name_en': 'Yūki Hayashi',
                          'wiki_ja': 'https://ja.wikipedia.org/wiki/%E6%9E%97%E7%A5%90%E5%B7%B1'})
        from bot.services.info_service import GoogleKGSCopyrightInfoService
        self.assertDictEqual(GoogleKGSCopyrightInfoService().get_info("zenki", "Zenki2", language_codes=("en",)),
                             {'kgs_url': 'http://g.co/kg/m/0cqf16',
                          'description': "Zenki is a Japanese manga series written by Kikuhide Tani and illustrated "
                                         "by Yoshihiro Kuroiwa. It was serialized in the Shueisha publication, Monthly"
                                         " Shōnen Jump from 1992 to 1996. ",
                          'name_en': 'Zenki',
                          'wiki_en': 'https://en.wikipedia.org/wiki/Zenki'})
