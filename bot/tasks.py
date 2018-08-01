import logging
import os
from urllib.parse import urlparse

from celery import shared_task
from django.conf import settings

from bot.services.download_service import DownloadService
from bot.services.info_service import InfoServiceBase, AtwikiInfoService, ASDBInfoService
from bot.services.media_service import MediaService
from bot.services.sakugabooru_service import SakugabooruService
from bot.services.translation_service import ANNArtistTranslationService, \
    GoogleAnimeTranslateService, MALAnimeTranslationService, BangumiAnimeTranslationService, TranslationServiceBase
from bot.services.weibo_service import WeiboService
from hub.models import Post, Tag

logger = logging.getLogger('bot.tasks')
TIME_LIMIT = settings.TASK_TIME_LIMIT


class TagInfoUpdateTask(object):
    def __init__(self, tag):
        assert isinstance(tag, Tag)
        self.tag = tag

    def _save_info_to_tag(self, info_dict):
        for k, v in info_dict.items():
            logger.info("Info [{}: {}] add to Tag[{}]".format(k, v, self.tag.name))
            if v:
                try:
                    self.tag.save_to_detail(k, v)
                except AttributeError:
                    logger.exception("Code[{}] is not existed.".format(k))

    def _get_and_save_info(self, service, name, **kwargs):
        logger.info("Tag[{}]: Getting result from {}".format(self.tag.name, service.__name__))
        service_instance = service()
        if isinstance(service_instance, TranslationServiceBase):
            info = service_instance.translate(name, **kwargs)
        elif isinstance(service_instance, InfoServiceBase):
            info = service_instance.get_info(name, **kwargs)
        else:
            raise NotImplemented
        if info:
            self._save_info_to_tag(info)
        return info

    def translate_artist(self):
        if self.tag.type != Tag.ARTIST:
            return
        name = self.tag.name.replace("_", " ")
        return self._get_and_save_info(ANNArtistTranslationService, name)

    def translate_copyright(self):
        if self.tag.type != Tag.COPYRIGHT:
            return
        name = self.tag.name.replace("_", " ")
        info = self._get_and_save_info(MALAnimeTranslationService, name)
        if info:
            info = self._get_and_save_info(BangumiAnimeTranslationService,
                                           info['name_ja'],
                                           name_en=name)
        if not info:
            try:
                source = self.tag.post_set.earliest('id').source
            except Post.DoesNotExist:
                source = ''
            if len(self.tag.name) > 6 and (len(source) < 10 or not bool(urlparse(source).netloc)):
                self._get_and_save_info(GoogleAnimeTranslateService, name)

    def get_additional_info(self):
        if self.tag.type not in (Tag.ARTIST, Tag.COPYRIGHT):
            return
        ja_name = self.tag.ja_name
        if not ja_name:
            return
        self._get_and_save_info(AtwikiInfoService, ja_name)
        if self.tag.type == Tag.COPYRIGHT:
            self._get_and_save_info(ASDBInfoService, ja_name)

    def save(self):
        return self.tag.save()

    def process(self):
        try:
            self.translate_artist()
            self.translate_copyright()
            self.get_additional_info()
        finally:
            return self.save()


def update_tags_info(*tags, update_tag_type=False):
    if update_tag_type:
        SakugabooruService().update_tags([tag.name for tag in tags], force_update=True)
    for tag in tags:
        TagInfoUpdateTask(tag).process()


@shared_task(soft_time_limit=TIME_LIMIT)
def update_tags_info_task(*tag_pks, update_tag_type=False):
    tags = Tag.objects.filter(pk__in=tag_pks)
    update_tags_info(*tags, update_tag_type=update_tag_type)


def update_posts(*posts):
    booru = SakugabooruService()
    try:
        logger.info("Updating posts {} from sakugabooru.".format([post.id for post in posts]))
        booru.update_posts(*[post.id for post in posts])
    finally:
        update_tags_info(*booru.created_tags)


@shared_task(soft_time_limit=TIME_LIMIT)
def update_posts_task(*post_pks):
    update_posts(*Post.objects.filter(pk__in=post_pks))


@shared_task(soft_time_limit=TIME_LIMIT)
def auto_update_posts():
    booru = SakugabooruService()
    try:
        logger.info("Updating posts from sakugabooru.")
        last_post = Post.objects.latest('id')
        page = 1
        posts = booru.update_posts_by_page(page=page)
        while posts[-1].id > last_post.id + 1:
            page += 1
            posts = booru.update_posts_by_page(page=page)
    except Post.DoesNotExist:
        booru.update_posts_by_page()
    except:
        logger.exception("Auto_update_posts failed.")
    finally:
        update_tags_info(*booru.created_tags)


@shared_task(soft_time_limit=TIME_LIMIT)
def post_weibo(post):
    logger.info("Post[{}]: Downloading media.".format(post.id))
    media_path = DownloadService().download_post_media(post)
    logger.info("Post[{}]: Transcoding media.".format(post.id))
    media_path = MediaService().transcoding_media(post, media_path)
    logger.info("Post[{}]: Sending weibo.".format(post.id))
    post.posted = True
    post.weibo = WeiboService().post_weibo(post, media_path)
    post.save()
    logger.info("Post[{}]: Posting Weibo Success. weibo_id[{}]".format(post.id, post.weibo.weibo_id))


@shared_task(soft_time_limit=TIME_LIMIT)
def auto_post_weibo():
    try:
        last_posted_post = Post.objects.filter(posted=True).latest('id')
        posts = Post.objects.filter(id__gt=last_posted_post.id, posted=False).order_by('id')
    except Post.DoesNotExist:
        posts = list(reversed(Post.objects.filter(posted=False).order_by('-id')[:20]))
    for post in posts:
        try:
            post_weibo(post)
        except RuntimeError as e:
            if '[SKIP]' in str(e):
                post.posted = True
                post.save()
                continue
            break
        except:
            logger.exception("Something went wrong while posting Post[{}].".format(post.id))
            break


@shared_task(soft_time_limit=TIME_LIMIT)
def clean_media():
    file_list = list()
    total_size = 0
    for start_path in (DownloadService.ROOT, MediaService.ROOT):
        for dirpath, dirnames, filenames in os.walk(start_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                fp_stat = os.stat(fp)
                total_size += fp_stat.st_size
                file_list.append((fp, fp_stat.st_size, fp_stat.st_ctime))
    file_list.sort(key=lambda x: x[-1])
    for fp, size, dummy in file_list:
        if total_size <= settings.MEDIA_MAX_SIZE:
            break
        try:
            os.remove(fp)
            total_size -= size
        except FileNotFoundError:
            total_size -= size
        except OSError:
            logger.exception("Error occurred while deleting file[{}].".format(fp))
            pass


@shared_task(soft_time_limit=TIME_LIMIT)
def bot_auto_task():
    auto_update_posts()
    auto_post_weibo()
    clean_media()
