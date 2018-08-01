import logging
import os

import requests
from django.conf import settings
from retrying import retry

from bot.constants import PLAIN_MEDIA_EXTS, SAKUGABOORU_MEDIA_DIR

logger = logging.getLogger('bot.services.download')


class DownloadService(object):
    """
    Download media from sakugabooru
    """
    ROOT = os.path.join(settings.MEDIA_ROOT, SAKUGABOORU_MEDIA_DIR)

    def __init__(self):
        self.session = requests.session()
        if not os.path.exists(self.ROOT):
            logger.info("Creating Directories. [{}]".format(self.ROOT))
            os.makedirs(self.ROOT)

    @retry(stop_max_attempt_number=3,
           wait_fixed=1000,
           retry_on_exception=lambda x: isinstance(x, OSError))
    def download_post_media(self, post):
        """
        :param post: hub.models.Post
        :return: path of the media
        """
        media_url = post.media_url
        path = os.path.join(self.ROOT, post.file_name)
        if os.path.exists(path):
            logger.info("Removing Existing File. [{}]".format(path))
            os.remove(path)
        if post.ext.lower() in PLAIN_MEDIA_EXTS and post.file_size > settings.WEIBO_IMAGE_MAX_SIZE:
            if post.sample_file_size and post.sample_file_size <= settings.WEIBO_IMAGE_MAX_SIZE:
                media_url = post.sample_url
                path = os.path.join(self.ROOT, post.sample_file_name)
                logger.info("Post[{}] media using sample image.".format(post.id))
            else:
                media_url = post.preview_url
                path = os.path.join(self.ROOT, post.preview_file_name)
                logger.info("Post[{}] media using preview image.".format(post.id))
        logger.info("Post[{}]: Downloading image from sakugabooru.".format(post.id))
        r = self.session.get(media_url, timeout=30)
        with open(path, 'wb') as f:
            f.write(r.content)
        return path
