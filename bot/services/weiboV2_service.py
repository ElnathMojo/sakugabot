import logging
import os

import requests
from retrying import retry

from bot.constants import SAKUGABOORU_POST_SAFE as SAKUGABOORU_POST
from bot.models import Credential
from bot.models import Weibo
from bot.services.utils.weiboV2 import WeiboClientV2
from hub.models import Tag

logger = logging.getLogger('bot.services.weiboV2')


class WeiboService(object):
    def __init__(self):
        try:
            self.credentials = Credential.objects.filter(enable=True).order_by('expires_at').last()
            self.client = WeiboClientV2(self.credentials.credentials)
        except Credential.DoesNotExist:
            raise RuntimeError("WeiboService init failed. Available Credential Doesn't Exist")

    @staticmethod
    def get_post_tags_info(post):
        tags_info = {'copyright': [],
                     'artist': [],
                     'tag': [],
                     'is_presumed': "原画"}
        for tag in post.tags.all():
            if tag.name == 'presumed':
                tags_info['is_presumed'] = "推测原画"
                continue
            tag_name = tag.weibo_name
            if tag.type == Tag.COPYRIGHT:
                tags_info['copyright'].append(tag_name)
            elif tag.type == Tag.ARTIST:
                tags_info['artist'].append(tag_name)
            else:
                tags_info['tag'].append(tag_name)
        for tag_type in ['copyright', 'artist', 'tag']:
            tags_info[tag_type] = "，".join(tags_info[tag_type])
        return tags_info

    def generate_weibo_content(self, post):
        tags_info = self.get_post_tags_info(post)

        url = "{}{}".format(SAKUGABOORU_POST, post.id)
        copyright_ = f"作品：{tags_info['copyright']}；" if tags_info['copyright'] else ""
        source = f"来源：{post.source}；" if post.source else ""
        artist = f"{tags_info['is_presumed']}：{tags_info['artist']}；" if tags_info['artist'] else ""
        tags = f"Tags：{tags_info['tag']}；" if tags_info['tag'] else ""
        uploader = f"上传者：{post.uploader.weibo_name}；" if post.uploader.weibo_name else ""
        return f"ID：{post.id}；{copyright_}{source}{artist}{tags}{uploader}{url} "

    @retry(stop_max_attempt_number=1,
           wait_fixed=10000,
           retry_on_exception=lambda x: '[RETRY]' in str(x))
    def post_weibo(self, post, image_path=None):
        """

        :param post: Post object
        :param image_path: Post image path
        :return: weibo object
        :raise:RuntimeError [SKIP] or [RETRY] //or [BLOCK]
        """
        try:
            size = os.path.getsize(image_path)
            if not size:
                raise FileNotFoundError
            logger.info("Image is about to be uploaded. Path: [{}]; Size: [{}]".format(image_path, size))
        except FileNotFoundError:
            logger.warning("Image invalid. Path: [{}]".format(image_path))
            raise RuntimeError("[SKIP]")
        text = self.generate_weibo_content(post)
        with open(image_path, 'rb') as pic:
            try:
                res = self.client.share(content=text, pic=pic)
                return Weibo.objects.create(weibo_id=res['idstr'],
                                            img_url=res['original_pic'],
                                            uid=self.credentials)
            except requests.exceptions.ConnectionError as e:
                logger.error("Post id[{}]: {}; Send Failed.".format(post.id, str(e)))
                raise RuntimeError("[RETRY]" + str(e))
            except RuntimeError as e:
                if '3022401' in str(e):
                    logger.error("Post id[{}]: {}; Image Upload Failed.".format(post.id, str(e)))
                    raise RuntimeError("[RETRY]" + str(e))
                logger.fatal("Post id[{}]: {}; Unknown Error.".format(post.id, str(e)))
                raise RuntimeError("[SKIP]" + str(e))
