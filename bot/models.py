from django.conf import settings
from django.db import models

from bot.constants import WEIBO_BASE, BASE_62_KEYS
from bot.services.utils.weiboV2 import rsa_encrypt, LOGIN_KEY, calculate_s


class Weibo(models.Model):
    weibo_id = models.CharField(primary_key=True, max_length=255)
    img_url = models.URLField(unique=True)
    create_time = models.DateTimeField(auto_now_add=True)
    uid = models.ForeignKey('bot.Credential', null=True, blank=True, default=None, on_delete=models.SET_DEFAULT)

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
        except Credential.DoesNotExist:
            return None


class Comment(models.Model):
    comment_id = models.CharField(primary_key=True, max_length=255)
    weibo_id = models.ForeignKey(Weibo, on_delete=models.CASCADE)


class Credential(models.Model):
    uid = models.CharField(max_length=64, primary_key=True)
    account = models.CharField(max_length=128)
    login_s = models.CharField(max_length=8, null=True, blank=True, default=None)
    aid = models.CharField(max_length=255, null=True, blank=True, default=None)
    password = models.CharField(max_length=255, null=True, blank=True, default=None)
    gsid = models.CharField(max_length=255, null=True, blank=True, default=None)
    raw_credentials = models.JSONField(null=True, blank=True, default=dict)
    access_token = models.CharField(max_length=128, null=True, blank=True, default=None)
    expires_at = models.DateTimeField(null=True, blank=True, default=None)
    enable = models.BooleanField(default=True)

    def set_password(self, password):
        self.password = rsa_encrypt(password, public_key=LOGIN_KEY)
        self.login_s = calculate_s(f"{self.account}{password}")

    @property
    def token(self):
        return {'uid': self.uid,
                'access_token': self.access_token,
                'expires_at': int(self.expires_at.timestamp())}

    @property
    def credentials(self):
        return {'uid': self.uid,
                'aid': self.aid,
                'gsid': self.gsid}
