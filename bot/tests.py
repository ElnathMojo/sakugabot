from django.test import SimpleTestCase, TestCase

from scripts.init import init_attributes


class TestTasks(TestCase):
    def setUp(self):
        init_attributes()

    def test_auto_task(self):
        from bot.tasks import bot_auto_task
        bot_auto_task()
        from hub.models import Post
        self.assertGreater(len(Post.objects.all()), 0)
        from hub.models import Node
        self.assertGreater(len(Node.objects.all()), 0)


class TestInfoServices(SimpleTestCase):

    def test_ann(self):
        from bot.services.info_service import ANNArtistInfoService
        self.assertEqual(ANNArtistInfoService().get_info("koji ito"),
                         {'name_ja': '伊藤浩二', 'ann_pid': 2253, 'name_en': 'Kōji Itō'})

    def test_mal(self):
        from bot.services.info_service import MALCopyrightInfoService
        self.assertEqual(MALCopyrightInfoService().get_info("zenki"),
                         {'mal_aid': 1573, 'name_ja': '鬼神童子ZENKI', 'name_en': 'Kishin Douji Zenki'})

    def test_bgm(self):
        from bot.services.info_service import BangumiCopyrightInfoService
        self.assertEqual(BangumiCopyrightInfoService().get_info("Violet Evergarden",
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
        self.assertEqual(AtwikiInfoService().get_info('高瀬健一', ), {'anime_wiki_id': '257', 'sakuga_wiki_id': '1203'})

    def test_asdb(self):
        from bot.services.info_service import ASDBCopyrightInfoService
        self.assertEqual(ASDBCopyrightInfoService().get_info('賭ケグルイ', ), {
            'anime_staff_database_link': 'http://seesaawiki.jp/w/radioi_34/d/%c5%d2%a5%b1%a5%b0%a5%eb%a5%a4',
            'name_ja': '賭ケグルイ'})

    def test_google(self):
        from bot.services.info_service import GoogleKGSArtistInfoService
        self.assertEqual(GoogleKGSArtistInfoService().get_info('yuki hayashi'),
                         {'kgs_url': 'http://g.co/kg/g/121wymf_',
                          'description': '林 祐己は、日本のアニメーター、キャラクターデザイナー。東映アニメーション所属。',
                          'name_ja': '林祐己',
                          'name_en': 'Yūki Hayashi',
                          'wiki_ja': 'https://ja.wikipedia.org/wiki/%E6%9E%97%E7%A5%90%E5%B7%B1'})
        from bot.services.info_service import GoogleKGSCopyrightInfoService
        self.assertEqual(GoogleKGSCopyrightInfoService().get_info("zenki", "Zenki2", language_codes=("en",)),
                         {'kgs_url': 'http://g.co/kg/m/0cqf16',
                          'description': "Zenki is a Japanese manga series written by Kikuhide Tani and illustrated "
                                         "by Yoshihiro Kuroiwa. It was serialized in the Shueisha publication, Monthly"
                                         " Shōnen Jump from 1992 to 1996. ",
                          'name_en': 'Zenki',
                          'wiki_en': 'https://en.wikipedia.org/wiki/Zenki'})
