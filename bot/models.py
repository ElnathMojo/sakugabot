from django.db import models


# Create your models here.

class Weibo(models.Model):
    weibo_id = models.CharField(primary_key=True, max_length=255)
    img_url = models.URLField(unique=True)
    create_time = models.DateTimeField(auto_now_add=True)


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
