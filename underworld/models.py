from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db import models


class IP(models.Model):
    address = models.GenericIPAddressField(primary_key=True)
    country = models.CharField(max_length=255, null=True, blank=True, default=None)
    country_code = models.CharField(max_length=255, null=True, blank=True, default=None)
    region = models.CharField(max_length=255, null=True, blank=True, default=None)
    region_name = models.CharField(max_length=255, null=True, blank=True, default=None)
    city = models.CharField(max_length=255, null=True, blank=True, default=None)
    zip = models.CharField(max_length=255, null=True, blank=True, default=None)
    lat = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True, default=None)
    lon = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True, default=None)
    timezone = models.CharField(max_length=255, null=True, blank=True, default=None)
    isp = models.CharField(max_length=255, null=True, blank=True, default=None)
    org = models.CharField(max_length=255, null=True, blank=True, default=None)
    _as = models.CharField(max_length=255, null=True, blank=True, default=None)


class AccessLog(models.Model):
    create_time = models.DateTimeField(auto_now_add=True)
    remote_addr = models.ForeignKey(IP, null=True, blank=True, default=None, on_delete=models.PROTECT,
                                    related_name='remote_addr_log')
    client_addr = models.ForeignKey(IP, null=True, blank=True, default=None, on_delete=models.PROTECT,
                                    related_name='client_addr_log')
    user = models.ForeignKey(get_user_model(), blank=True, null=True, default=None, on_delete=models.PROTECT)
    request_method = models.CharField(max_length=255, null=True, blank=True, default=None)
    request_path = models.TextField(null=True, blank=True, default=None)
    status = models.IntegerField(null=True, blank=True, default=None)
    body_bytes_sent = models.IntegerField(null=True, blank=True, default=None)
    http_referer = models.TextField(null=True, blank=True, default=None)
    http_user_agent = models.TextField(null=True, blank=True, default=None)
    forwarded_for = ArrayField(
        models.GenericIPAddressField(default=None, null=True, blank=True),
        blank=True,
        default=list
    )
    class Meta:
        get_latest_by = "create_time"
        indexes = [
            models.Index(fields=['create_time']),
        ]

