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

    def test_translation_services(self):
        from bot.services.translation_service import ANNArtistTranslationService
        self.assertEqual(ANNArtistTranslationService().translate("koji ito"),
                         {'name_ja': '伊藤浩二', 'ann_pid': 2253, 'name_en': 'Kōji Itō'})
        from bot.services.translation_service import MALAnimeTranslationService
        self.assertEqual(MALAnimeTranslationService().translate("zenki"),
                         {'mal_aid': 1573, 'name_ja': '鬼神童子ZENKI', 'name_en': 'Kishin Douji Zenki'})
        from bot.services.translation_service import BangumiAnimeTranslationService
        self.assertEqual(BangumiAnimeTranslationService().translate("ヴァイオ一レット・エヴァーガーデン"),
                         {'name_ja': 'ヴァイオレット・エヴァーガーデン', 'bgm_sid': 183878, 'name_zh': '紫罗兰永恒花园'})
        from bot.services.translation_service import GoogleTranslateService
        self.assertEqual(GoogleTranslateService().translate("maken ki! two"),
                         {'name_zh': '魔剑姬！', 'name_ja': 'マケン姫っ!', 'name_en': 'Maken-ki!'})

    def test_info_services(self):
        from bot.services.info_service import AtwikiInfoService
        self.assertEqual(AtwikiInfoService().get_info('高瀬健一', ), {'anime_wiki_id': '257', 'sakuga_wiki_id': '1203'})
        from bot.services.info_service import ASDBInfoService
        self.assertEqual(ASDBInfoService().get_info('賭ケグルイ', ), {
            'anime_staff_database_link': 'http://seesaawiki.jp/w/radioi_34/d/%c5%d2%a5%b1%a5%b0%a5%eb%a5%a4'})
