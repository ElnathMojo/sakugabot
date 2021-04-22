import logging
import os
import random
from datetime import timedelta
from urllib.parse import urlparse

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.utils.timezone import now
from requests import HTTPError
from rest_framework_simplejwt.token_blacklist.management.commands import flushexpiredtokens

from bot.models import Weibo
from bot.services.download_service import DownloadService
from bot.services.info_service import AtwikiInfoService, ASDBCopyrightInfoService, ANNArtistInfoService, \
    GoogleKGSArtistInfoService, MALCopyrightInfoService, BangumiCopyrightInfoService, GoogleKGSCopyrightInfoService
from bot.services.media_service import MediaService
from bot.services.sakugabooru_service import SakugabooruService
from bot.services.weiboV2_service import WeiboService
from hub.models import Post, Tag, Node

logger = logging.getLogger('bot.tasks')
TIME_LIMIT = settings.TASK_TIME_LIMIT


class TagInfoUpdateTask(object):
    def __init__(self, tag, overwrite=False):
        assert isinstance(tag, Tag)
        self.tag = tag
        self.overwrite = overwrite
        self.info = dict()

    def _save_info_to_tag(self):
        for k, v in self.info.items():
            if v:
                try:
                    logger.info("Info [{}: {}] is being added "
                                "to Tag[{}]. Overwrite: {}".format(k,
                                                                   v,
                                                                   self.tag.name,
                                                                   self.overwrite))
                    self.tag.save_to_detail(k, v, self.overwrite)
                except AttributeError:
                    pass

    def _get_and_save_info(self, service, *names, overwrite_keys=(), **kwargs):
        logger.info("Tag[{}]: Getting result from {} with names {}".format(self.tag.name, service.__name__, names))
        service_instance = service()
        info = service_instance.get_info(*names, **kwargs)
        for k, v in info.items():
            if k in overwrite_keys:
                self.info[k] = v
                continue
            self.info.setdefault(k, v)

    def get_values_from_info(self, *keys):
        return [self.info.get(key, None) for key in keys if self.info.get(key, None)]

    def translate_artist(self):
        if self.tag.type != Tag.ARTIST:
            return
        name = self.tag.name.replace("_", " ")
        self._get_and_save_info(ANNArtistInfoService, name)
        names = [name] + self.get_values_from_info('name_ja')
        self._get_and_save_info(GoogleKGSArtistInfoService,
                                *names,
                                overwrite_keys=('description',))

    def translate_copyright(self):
        if self.tag.type != Tag.COPYRIGHT:
            return
        name = self.tag.name.replace("_", " ")
        self._get_and_save_info(MALCopyrightInfoService, name)
        names = [name] + self.get_values_from_info('name_ja')
        self._get_and_save_info(BangumiCopyrightInfoService,
                                *names,
                                overwrite_keys=("name_ja",))
        try:
            source = self.tag.post_set.latest('id').source
        except Post.DoesNotExist:
            source = ''
        if len(self.tag.name) > 6 and (len(source) < 10 or not bool(urlparse(source).netloc)):
            names = [name] + self.get_values_from_info('name_ja', 'name_zh')
            self._get_and_save_info(GoogleKGSCopyrightInfoService,
                                    *names,
                                    overwrite_keys=('description',))

    def get_additional_info(self):
        if self.tag.type not in (Tag.ARTIST, Tag.COPYRIGHT):
            return
        ja_names = []
        if self.tag.ja_name:
            ja_names.append(self.tag.ja_name)
        ja_names.extend(self.get_values_from_info('name_ja'))
        if not ja_names:
            ja_names = [self.tag.name.replace("_", " ")]
        self._get_and_save_info(AtwikiInfoService, *ja_names)
        if self.tag.type == Tag.COPYRIGHT:
            self._get_and_save_info(ASDBCopyrightInfoService, *ja_names)

    @transaction.atomic
    def save(self):
        self.tag.refresh_from_db()
        self._save_info_to_tag()
        return self.tag.save()

    def process(self):
        try:
            self.translate_artist()
            self.translate_copyright()
            self.get_additional_info()
        finally:
            return self.save()


def update_tags_info(*tags, update_tag_type=False, overwrite=False):
    if update_tag_type:
        tags = SakugabooruService().update_tags([tag.name for tag in tags], force_update=True)
    for tag in tags:
        TagInfoUpdateTask(tag, overwrite).process()


@shared_task(soft_time_limit=TIME_LIMIT)
def update_tags_info_task(*tag_pks, update_tag_type=False, overwrite=False):
    tags = Tag.objects.filter(pk__in=tag_pks)
    update_tags_info(*tags, update_tag_type=update_tag_type, overwrite=overwrite)


@shared_task
def update_all_tags_info(update_tag_type=True, overwrite=True):
    tags = Tag.objects.filter(type__in=[Tag.ARTIST, Tag.COPYRIGHT])
    update_tags_info(*tags, update_tag_type=update_tag_type, overwrite=overwrite)


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
        while posts[-1].id > last_post.id + 1 or page < 3:
            page += 1
            posts = booru.update_posts_by_page(page=page)
    except Post.DoesNotExist:
        booru.update_posts_by_page()
    except:
        logger.exception("Auto_update_posts failed.")
    finally:
        update_tags_info(*booru.created_tags)


def post_weibo(*posts):
    weibo_service = WeiboService()
    for post in posts:
        try:
            logger.info("Post[{}]: Downloading media.".format(post.id))
            media_path = DownloadService().download_post_media(post)
            logger.info("Post[{}]: Transcoding media.".format(post.id))
            media_path = MediaService().transcoding_media(post, media_path)
            logger.info("Post[{}]: Sending weibo.".format(post.id))
            post.posted = True
            post.weibo = weibo_service.post_weibo(post, media_path)
            post.save()
            logger.info("Post[{}]: Posting Weibo Success. weibo_id[{}]".format(post.id, post.weibo.weibo_id))
        except HTTPError as e:
            if '404' in str(e):
                post.posted = True
                post.save()
                continue
        except RuntimeError as e:
            if '[SKIP]' in str(e):
                post.posted = True
                post.save()
                continue
            break
        except:
            post.posted = True
            post.save()
            logger.exception("Something went wrong while posting Post[{}].".format(post.id))
            raise


@shared_task(soft_time_limit=TIME_LIMIT)
def post_weibo_task(*post_pks):
    post_weibo(*Post.objects.filter(pk__in=post_pks).order_by('id'))


def check_status():
    last_weibo = Weibo.objects.last()
    fails = Post.objects.filter(id__gt=last_weibo.post.id,
                                update_time__gt=last_weibo.create_time - timedelta(hours=settings.MAX_PENDING_HOURS),
                                posted=True,
                                weibo__isnull=True)
    if len(fails) >= 5:
        return False
    return True


@shared_task(soft_time_limit=TIME_LIMIT)
def auto_post_weibo():
    if not check_status():
        logger.error("More than 5 fails. Posting has Stopped!")
        return
    try:
        last_posted_post = Post.objects.filter(posted=True).latest('id')

        posts = Post.objects.filter(
            created_at__gt=last_posted_post.created_at - timedelta(hours=settings.MAX_PENDING_HOURS),
            posted=False,
            is_shown=True).exclude(
            Q(uploader__in_blacklist=True) | Q(uploader__in_whitelist=False, is_pending=True)).order_by('id')
    except Post.DoesNotExist:
        posts = list(reversed(Post.objects.filter(posted=False,
                                                  is_shown=True).order_by('-id')[:20]))
    if not posts:
        logger.info("There's no need to post weibo.")
    post_weibo(*posts[:random.randint(1, 2)])


@shared_task()
def auto_post_weibo_with_random_delay():
    if random.random() < 0.8:
        waiting_sec = random.randint(0, 300)
        logger.info("Try to post weibo in {} seconds.".format(waiting_sec))
        auto_post_weibo.apply_async(eta=now() + timedelta(seconds=waiting_sec))


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
            logger.info("File[{}] has been removed.".format(fp))
        except FileNotFoundError:
            total_size -= size
        except OSError:
            logger.exception("Error occurred while deleting file[{}].".format(fp))
            raise


@shared_task(soft_time_limit=TIME_LIMIT)
def clean_nodes():
    annotated_nodes = Node.objects.annotate(n_histories=Count('histories'))
    orphans = annotated_nodes.filter(n_histories=0)
    nodes = [{'attribute': node.attribute.code, 'value': node._value} for node in orphans]
    orphans.delete()
    if nodes:
        logger.info("Following Nodes have been deleted.: {}".format(nodes))


@shared_task(soft_time_limit=TIME_LIMIT)
def bot_auto_task():
    try:
        auto_update_posts()
        auto_post_weibo()
    finally:
        clean_media()


@shared_task
def clean_expired_tokens():
    flushexpiredtokens.Command().handle()
