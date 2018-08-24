from django.conf import settings
from django.db import models

# Create your models here.

from bot.constants import WEIBO_BASE, BASE_62_KEYS


class Weibo(models.Model):
    weibo_id = models.CharField(primary_key=True, max_length=255)
    img_url = models.URLField(unique=True)
    create_time = models.DateTimeField(auto_now_add=True)
    uid = models.ForeignKey('bot.AccessToken', null=True, blank=True, default=None, on_delete=models.SET_DEFAULT)

    @staticmethod
    def _encode62(n, minlen=4):
        base = len(BASE_62_KEYS)
        chs = list()
        while n > 0:
            r = n % base
            n //= base
            chs.append(BASE_62_KEYS[r])
        if len(chs) > 0:
            chs.reverse()
        else:
            chs.append(BASE_62_KEYS[0])
        s = ''.join(chs)
        s = BASE_62_KEYS[0] * max(minlen - len(s), 0) + s
        return s

    @property
    def mid(self):
        mid = str()
        for code in [self.weibo_id[i - 7 if i - 7 >= 0 else 0:i] for i in range(len(self.weibo_id), 0, -7)]:
            mid = self._encode62(int(code)) + mid
        return mid.lstrip('0')

    @property
    def weibo_url(self):
        try:
            return "{}/{}/{}".format(WEIBO_BASE, self.uid.uid if self.uid else settings.WEIBO_UID, self.mid)
        except AccessToken.DoesNotExist:
            return None


class Comment(models.Model):
    comment_id = models.CharField(primary_key=True, max_length=255)
    weibo_id = models.ForeignKey(Weibo, on_delete=models.CASCADE)


class AccessToken(models.Model):
    uid = models.CharField(max_length=64, primary_key=True)
    access_token = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    enable = models.BooleanField(default=True)

    @property
    def token(self):
        return {'uid': self.uid,
                'access_token': self.access_token,
                'expires_at': int(self.expires_at.timestamp())}
