import logging
import os
from collections import OrderedDict

from django.conf import settings
from moviepy.editor import VideoFileClip
from retrying import retry

from bot.constants import PALETTE_FILE_NAME, WEIBO_MEDIA_DIR, ANIMATED_MEDIA_EXTS
from bot.services.ultils.ffmpy3 import FFmpeg, FFRuntimeError

logger = logging.getLogger('bot.services.media')

WEIBO_IMAGE_MAX_SIZE = settings.WEIBO_IMAGE_MAX_SIZE
WEIBO_GIF_WIDTH = settings.WEIBO_GIF_WIDTH
WEIBO_GIF_FPS = settings.WEIBO_GIF_FPS


class MediaService(object):
    ROOT = os.path.join(settings.MEDIA_ROOT, WEIBO_MEDIA_DIR)
    PALETTE_FILE = os.path.join(settings.TMP_DIR, PALETTE_FILE_NAME)

    def __init__(self, fps=WEIBO_GIF_FPS, width=WEIBO_GIF_WIDTH, max_size=WEIBO_IMAGE_MAX_SIZE):
        self.fps = fps
        self.width = width
        self.max_size = max_size
        if not os.path.exists(self.ROOT):
            os.makedirs(self.ROOT)

    @retry(stop_max_attempt_number=3,
           wait_fixed=1000,
           retry_on_exception=lambda x: isinstance(x, OSError))
    def transcoding_media(self, post, media_path):
        if post.ext.lower() not in ANIMATED_MEDIA_EXTS:
            logger.info("Media[{}]: No need for transcoding.".format(media_path))
            return media_path
        if post.ext.lower() == "gif":
            return self.gif_split(media_path)
        path = os.path.join(self.ROOT, post.weibo_file_name)
        if os.path.exists(path):
            logger.info("Removing Existing File. [{}]".format(path))
            os.remove(path)
        return self.gif_make(media_path, path)

    def gif_make(self, input, output):
        logger.info("Media[{}]: Transcoding media(highQ)".format(input))
        try:
            self._highQ(input, output)
            if os.path.getsize(output) < self.max_size:
                return output
            self.gif_optimize(output)
            if os.path.getsize(output) < self.max_size:
                return output
        except FFRuntimeError:
            logger.warning("Something went wrong when transcoding [{}](highQ).".format(input))
        try:
            os.remove(output)
        except FileNotFoundError:
            pass
        logger.info("Media[{}]: Transcoding media(nomQ)".format(input))
        self._nomQ(input, output)
        if os.path.getsize(output) < self.max_size:
            return output
        return self.gif_split(output)

    @staticmethod
    @retry(stop_max_attempt_number=3,
           wait_fixed=3000)
    def _force_rename(src, dst):
        try:
            os.remove(dst)
        except FileNotFoundError:
            pass
        os.rename(src, dst)
        return dst

    def gif_optimize(self, target):
        logger.info("Media[{}]: Optimizing gif".format(target))
        path, filename = os.path.split(target)
        filename = os.path.splitext(filename)[0]
        new_filename = 'new_{}.gif'.format(filename)
        new_path = os.path.join(path, new_filename)
        if os.path.exists(new_path):
            os.remove(new_path)
        clip = VideoFileClip(target)
        clip.write_gif(new_path, program='ffmpeg')
        clip.close()
        self._force_rename(new_path, target)

    def gif_split(self, target):
        if os.path.getsize(target) <= self.max_size:
            return target
        self.gif_optimize(target)

        logger.info("Media[{}]: Splitting gif".format(target))

        size = os.path.getsize(target)
        path, filename = os.path.split(target)
        filename = os.path.splitext(filename)[0]
        new_filename = 'new_{}.gif'.format(filename)
        new_path = os.path.join(path, new_filename)
        if os.path.exists(new_path):
            os.remove(new_path)

        while size > self.max_size:
            clip = VideoFileClip(target)
            end = clip.duration * self.max_size / size - 1
            clip = clip.subclip(0, end)
            clip.write_gif(new_path, program='ffmpeg')
            clip.close()
            self._force_rename(new_path, target)

            size = os.path.getsize(target)

        return target

    def _highQ(self, input, output):
        if os.path.isfile(self.PALETTE_FILE):
            os.remove(self.PALETTE_FILE)
        ff = FFmpeg(
            inputs={input: '-v warning'},
            outputs={
                self.PALETTE_FILE: ['-vf',
                                    "fps={},scale={}:-1:flags=lanczos,palettegen".format(self.fps, self.width),
                                    '-y']}
        )

        ff.run()

        ff = FFmpeg(
            inputs=OrderedDict([(input, '-v warning'),
                                (self.PALETTE_FILE, None)]),
            outputs={
                output: ['-lavfi',
                         "fps={},scale={}:-1:flags=lanczos [x]; [x][1:v] paletteuse".format(self.fps, self.width),
                         '-y']}
        )

        ff.run()

    def _nomQ(self, input, output):
        ff = FFmpeg(
            inputs={input: '-v warning'},
            outputs={
                output: ['-vf',
                         "fps={},scale={}:-1:flags=lanczos".format(self.fps, self.width),
                         '-gifflags', '+transdiff', '-y']}
        )

        ff.run()
