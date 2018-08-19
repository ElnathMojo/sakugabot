import logging
import os

from django.conf import settings

from bot.constants import SAKUGABOORU_POST
from bot.models import AccessToken, Weibo
from bot.services.ultils.weibo import Client
from hub.models import Tag, Uploader

logger = logging.getLogger('bot.services.weibo')


class WeiboService(object):
    def __init__(self):
        try:
            self.token = AccessToken.objects.filter(enable=True).order_by('expires_at').last()
            self.client = Client(settings.WEIBO_API_KEY,
                                 settings.WEIBO_API_SECRET,
                                 settings.WEIBO_REDIRECT_URI,
                                 token=self.token.token)
        except AccessToken.DoesNotExist:
            raise RuntimeError("WeiboService init failed. Available AccessToken Doesn't Exist")

    @staticmethod
    def get_post_uploader_name(post):
        try:
            uploader = Uploader.objects.get(name=post.uploader)
            return uploader.override_name
        except Uploader.DoesNotExist:
            return post.uploader

    @staticmethod
    def get_post_tags_info(post):
        tags_info = {'copyright': [],
                     'artist': [],
                     'tag': [],
                     'is_presumed': False}
        for tag in post.tags.all():
            if tag.name == 'presumed':
                tags_info['is_presumed'] = True
                continue
            tag_name = tag.weibo_name
            if tag.type == Tag.COPYRIGHT:
                tags_info['copyright'].append(tag_name)
            elif tag.type == Tag.ARTIST:
                tags_info['artist'].append(tag_name)
            else:
                tags_info['tag'].append(tag_name)
        return tags_info

    @staticmethod
    def _loop_shorten(shorten, index, key, text_dict, data_source):
        while shorten > 0 and data_source:
            shorten -= 1
            data_source.pop()
        tag_text = "，".join(data_source)
        if tag_text:
            text_dict[index] = "{}：{}".format(key, tag_text)
        return shorten

    @staticmethod
    def _single_shorten(shorten, index, key, text_dict, data_source):
        if shorten > 0:
            shorten -= 1
        else:
            if data_source:
                text_dict[index] = "{}：{}".format(key, data_source)
        return shorten

    def generate_weibo_content(self, post, shorten=0):
        tags_info = self.get_post_tags_info(post)

        text_dict = dict()

        text_dict[0] = "ID：{}".format(post.id)

        for args in [
            (self._single_shorten, 2, '来源', text_dict, post.source),
            (self._single_shorten, 5, '上传者', text_dict, self.get_post_uploader_name(post)),
            (self._loop_shorten, 4, 'Tags', text_dict, tags_info['tag']),
            (self._loop_shorten, 1, '作品', text_dict, tags_info['copyright']),
            (self._loop_shorten, 3, '推测原画' if tags_info['is_presumed'] else '原画', text_dict, tags_info['artist']),
        ]:
            shorten = args[0](shorten, *args[1:])

        text_dict[6] = "{}{}".format(SAKUGABOORU_POST, post.id)
        return "；".join([x[-1] for x in sorted(text_dict.items(), key=lambda x: x[0])])

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
        shorten = 0
        while shorten < 10:
            try:
                with open(image_path, 'rb') as pic:
                    res = self.client.post('statuses/share', status=text, pic=pic)
                    return Weibo.objects.create(weibo_id=res['id'],
                                                img_url=res['original_pic'],
                                                uid=self.token)
            except RuntimeError as e:
                if any(x in str(e) for x in ['20012', '20013']):
                    logger.warning("Post id[{}]: {}; Try to Shorten.".format(post.id, str(e)))
                    shorten += 1
                    text = self.generate_weibo_content(post, shorten)
                elif any(x in str(e) for x in ['20018', '20020', '20021']):
                    logger.error("Post id[{}]: {}; Skip.".format(post.id, str(e)))
                    raise RuntimeError("[SKIP]")
                elif any(x in str(e) for x in ['20016', '20017', '20019']):
                    logger.error("Post id[{}]: {}; Wait and Retry.".format(post.id, str(e)))
                    raise RuntimeError("[RETRY]")
                else:
                    logger.fatal("Post id[{}]: {}; Unknown Error.".format(post.id, str(e)))
                    raise RuntimeError("[RETRY]")
        logger.error("Post id[{}]: Shorten Loop Count Limit Exceeded; Skip.".format(post.id))
        raise RuntimeError("[SKIP]")
