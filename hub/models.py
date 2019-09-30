import collections
import json
from datetime import datetime, date, time

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField, ArrayField
from django.db import models, transaction
from django.utils.dateparse import parse_date, parse_time, parse_datetime

from bot.constants import SAKUGABOORU_DATA_URL, SAKUGABOORU_PREVIEW_URL, SAKUGABOORU_PREVIEW_EXT, SAKUGABOORU_POST, \
    ANIMATED_MEDIA_EXTS
from hub.fields import HashField, hash_it, LengthField
from hub.ultils.JSONEncoder import DjangoJSONEncoder
from sakugabot.settings import NEW_COMMIT_SECONDS


class Uploader(models.Model):
    name = models.CharField(max_length=255, primary_key=True)
    override_name = models.CharField(max_length=255, default=None, null=True, blank=True)
    in_whitelist = models.BooleanField(default=False)
    in_blacklist = models.BooleanField(default=False)

    @property
    def weibo_name(self):
        if self.override_name:
            return self.override_name
        return self.name


class Tag(models.Model):
    GENERAL = 0
    ARTIST = 1
    COPYRIGHT = 3
    TERMINOLOGY = 4
    META = 5
    TYPE_CHOICES = (
        (GENERAL, 'General'),
        (ARTIST, 'Artist'),
        (COPYRIGHT, 'Copyright'),
        (TERMINOLOGY, 'Terminology'),
        (META, 'Meta')
    )
    type = models.SmallIntegerField(choices=TYPE_CHOICES, default=GENERAL)
    name = models.CharField(max_length=255, primary_key=True)

    override_name = models.CharField(max_length=255, default=None, null=True, blank=True)

    deletion_flag = models.BooleanField(default=False)
    is_editable = models.BooleanField(default=True)

    like_count = models.IntegerField(default=0)

    _detail = JSONField(encoder=DjangoJSONEncoder, default=dict, blank=True)
    order_of_keys = ArrayField(models.CharField(max_length=255), default=list, blank=True)

    @property
    def detail(self):
        return self._detail

    @detail.setter
    def detail(self, value):
        self._detail = value
        self.refresh_order()

    @property
    def snapshot_latest(self):
        try:
            return self.snapshots.latest('update_time')
        except TagSnapshot.DoesNotExist:
            return None

    @property
    def weibo_name(self):
        if self.override_name:
            return self.override_name
        return self.main_name

    @property
    def main_name(self):
        for code in ["name_main", "name_zh"]:
            name = self._detail.get(code, None)
            if name:
                return name
        if self.type == self.ARTIST:
            name = self._detail.get('name_ja', None)
            if name:
                return name
        return self.name.replace("_", " ").title()

    @property
    def ja_name(self):
        name_ja = self._detail.get('name_ja', None)
        if name_ja:
            return name_ja
        if self.type == self.ARTIST and self.override_name:
            return self.override_name
        return None

    def names(self):
        name_codes = [x.code for x in Attribute.objects.filter(code__startswith='name')]
        return dict(filter(lambda x: x[0] in name_codes, list(self._detail.items())))

    @property
    def ordered_detail(self):
        result = collections.OrderedDict()
        for key in self.order_of_keys:
            result[key] = self._detail[key]
        return result

    def save_to_detail(self, key, value, overwrite=True):
        attr = Attribute.get_attr_by_code(key, self.type)
        if not attr:
            raise AttributeError("Attribute {} does not exist.".format(key))
        if not isinstance(value, attr.type_class):
            value = attr.type_class(value)
        if overwrite:
            self._detail[key] = value
        else:
            self._detail.setdefault(key, value)
        if key not in self.order_of_keys:
            self.order_of_keys.append(key)

    def _gen_hash_if_changed(self):
        hash = hash_it(json.dumps(self.ordered_detail, cls=DjangoJSONEncoder))
        if hash == getattr(self.snapshot_latest, 'hash', None):
            return None
        return hash

    def _gen_snapshot_note(self, old, new, hash):
        notes = []
        try:
            snapshot = self.snapshots.filter(hash=hash).latest('update_time')
            notes.append(
                "Revert to id:{}".format(snapshot.id)
            )
        except TagSnapshot.DoesNotExist:
            pass
        old_keys = list(old.keys())
        change = list()
        add = list()
        for new_key in new.keys():
            if new_key in old_keys:
                if old[new_key] != new[new_key]:
                    change.append(new_key)
                old_keys.remove(new_key)
            else:
                add.append(new_key)
        if change:
            notes.append("Change:{}".format(",".join(change)))
        if add:
            notes.append("Add:{}".format(",".join(add)))
        if old_keys:
            notes.append("Delete:{}".format(",".join(old_keys)))
        if not notes:
            notes.append("Order changed")

        return ";".join(notes)

    def _create_snapshot(self, user, hash, content):
        snapshot = self.snapshot_latest
        if not snapshot:
            snapshot = TagSnapshot(tag=self, _user=user, hash=hash, note="Init")
        else:
            seconds_since_last_create = (datetime.utcnow().timestamp() - snapshot.create_time.timestamp())
            if not ((snapshot.raw_user == user and seconds_since_last_create <= NEW_COMMIT_SECONDS) or
                    snapshot.raw_user is user is None):
                snapshot = TagSnapshot(tag=self, _user=user, hash=hash,
                                       note=self._gen_snapshot_note(snapshot.content, content, hash))
            else:
                query = self.snapshots.order_by('-update_time')
                if len(query) > 1:
                    if query[1].hash == hash:
                        snapshot.delete()
                        return
                    snapshot.note = self._gen_snapshot_note(query[1].content, content, hash)
                snapshot.hash = hash
        snapshot.save(content=content)

    @staticmethod
    def gen_order_of_keys(order, keys):
        order_of_keys = [k for k in order if k in keys]
        order_of_keys += [k for k in keys if k not in order_of_keys]
        return order_of_keys

    def refresh_order(self):
        self.order_of_keys = self.gen_order_of_keys(self.order_of_keys, self._detail.keys() if self._detail else [])

    @transaction.atomic
    def save(self, *args, **kwargs):
        user = kwargs.pop('editor', None)
        self.refresh_order()

        super(Tag, self).save(*args, **kwargs)
        hash = self._gen_hash_if_changed()
        if hash:
            self._create_snapshot(user, hash, self.ordered_detail)

    class Meta:
        indexes = [
            models.Index(fields=['type', 'name']),
        ]


class Attribute(models.Model):
    code = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255, null=True, blank=True, default=None)
    alias = JSONField(encoder=DjangoJSONEncoder, default=dict, blank=True)

    INTEGER = 0
    FLOAT = 1
    STRING = 3
    DATETIME = 4
    DATE = 5
    TIME = 6
    FORMAT = 9
    TYPE_CHOICES = (
        (INTEGER, 'Integer'),
        (FLOAT, 'Float'),
        (STRING, 'String'),
        (DATETIME, 'Datetime'),
        (DATE, 'Date'),
        (TIME, 'Time'),
    )
    TYPE_MAPS = {
        INTEGER: int,
        FLOAT: float,
        STRING: str,
        DATETIME: datetime,
        DATE: date,
        TIME: time
    }
    FORM_FIELD_MAP = {
        INTEGER: forms.IntegerField,
        FLOAT: forms.FloatField,
        STRING: forms.CharField,
        DATETIME: forms.DateTimeField,
        DATE: forms.DateField,
        TIME: forms.TimeField
    }
    type = models.SmallIntegerField(choices=TYPE_CHOICES)

    format = models.TextField(null=True, blank=True, default=None)
    regex = models.CharField(max_length=255, null=True, blank=True, default=None)
    related_types = ArrayField(base_field=models.SmallIntegerField(choices=Tag.TYPE_CHOICES,
                                                                   default=Tag.GENERAL),
                               blank=True)
    order = models.PositiveIntegerField(default=0)

    @property
    def type_class(self):
        return self.TYPE_MAPS[self.type]

    @property
    def form_field_class(self):
        return self.FORM_FIELD_MAP[self.type]

    def serialize_value(self, value):
        if not isinstance(value, self.type_class):
            raise TypeError("Object[type: {}] is not an instance of {}".format(type(value), self.type_class))

        if self.type in [Attribute.DATE, Attribute.TIME, Attribute.DATETIME]:
            value = value.isoformat()
            if value.endswith('+00:00'):
                value = value[:-6] + 'Z'
            return value
        else:
            return str(value)

    def deserialize_value(self, value):
        if self.type == Attribute.DATE:
            return parse_date(value)
        elif self.type == Attribute.TIME:
            return parse_time(value)
        elif self.type == Attribute.DATETIME:
            return parse_datetime(value)
        else:
            return self.type_class(value)

    @staticmethod
    def get_attr_by_code(code, type=None):
        res = Attribute.objects.filter(code=code)
        if type:
            res = res.filter(related_types__contains=[type])
        if res:
            return res[0]
        return None


class TagSnapshot(models.Model):
    tag = models.ForeignKey("hub.Tag", related_name="snapshots", on_delete=models.CASCADE)
    update_time = models.DateTimeField(auto_now=True)
    hash = models.CharField(max_length=40, null=False)
    note = models.TextField(default=None, null=True, blank=True)
    _user = models.ForeignKey(get_user_model(), blank=True, null=True, default=None, on_delete=models.PROTECT)
    create_time = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        content = kwargs.pop('content', None)
        super(TagSnapshot, self).save(*args, **kwargs)
        if content is not None:
            self.save_content(content)

    @property
    def content(self):
        d = collections.OrderedDict()
        for node in self.nodes.order_by("tagsnapshotnoderelation__order"):
            d[node.attribute.code] = node.node_value
        return d

    def save_content(self, content):
        nodes = list()
        for i, (key, value) in enumerate(content.items()):
            attribute = Attribute.get_attr_by_code(key)
            if not attribute:
                raise AttributeError("Attribute {} does not exist.".format(key))
            try:
                obj_value = attribute.serialize_value(value)
                hash_value = hash_it(obj_value)
                node = Node.objects.get(attribute=attribute,
                                        hash=hash_value,
                                        length=len(obj_value))
            except Node.DoesNotExist:
                node = Node.create(attribute=attribute,
                                   value=value)

            nodes.append(TagSnapshotNodeRelation.objects.update_or_create(tag_snapshot=self,
                                                                          node=node,
                                                                          defaults={
                                                                              'order': i
                                                                          })[0])
        TagSnapshotNodeRelation.objects.filter(tag_snapshot=self).exclude(id__in=[o.id for o in nodes]).delete()
        # remove useless node

    @property
    def raw_user(self):
        return self._user

    @raw_user.setter
    def raw_user(self, value):
        self._user = value

    @property
    def user(self):
        if self._user:
            return self._user
        return User(username="System")

    @user.setter
    def user(self, value):
        if isinstance(value, get_user_model()):
            self._user = value
        else:
            self._user = None

    @property
    def user_name(self):
        return self.user.username

    class Meta:
        get_latest_by = "update_time"
        indexes = [
            models.Index(fields=['_user', 'update_time']),
            models.Index(fields=['update_time']),
            models.Index(fields=['tag', 'update_time']),
            models.Index(fields=['hash'])
        ]


class Node(models.Model):
    attribute = models.ForeignKey("hub.Attribute", on_delete=models.CASCADE)
    _value = models.TextField()
    hash = HashField(original='_value')
    length = LengthField(original='_value')
    histories = models.ManyToManyField(TagSnapshot, through="hub.TagSnapshotNodeRelation", related_name="nodes")

    @property
    def node_value(self):
        return self.attribute.deserialize_value(self._value)

    @node_value.setter
    def node_value(self, value):
        self._value = self.attribute.serialize_value(value)

    @classmethod
    def create(cls, attribute, value):
        node = cls(attribute=attribute)
        node.node_value = value
        node.save()
        return node

    class Meta:
        unique_together = ('attribute', 'hash', 'length')


class TagSnapshotNodeRelation(models.Model):
    tag_snapshot = models.ForeignKey("hub.TagSnapshot", on_delete=models.CASCADE)
    node = models.ForeignKey("hub.Node", on_delete=models.CASCADE)
    order = models.IntegerField()

    class Meta:
        unique_together = ("tag_snapshot", "node", "order")
        indexes = [
            models.Index(fields=['tag_snapshot', 'order']),
        ]


class Post(models.Model):
    id = models.IntegerField(primary_key=True)
    source = models.TextField(blank=True, null=True, default=None)
    file_size = models.IntegerField(default=0)
    is_shown = models.BooleanField(default=True)
    is_pending = models.BooleanField(default=True)
    md5 = models.CharField(max_length=33)
    ext = models.CharField(max_length=8)
    created_at = models.DateTimeField(null=True)
    score = models.PositiveIntegerField(default=0)
    rating = models.CharField(max_length=10, default='s')
    sample_url = models.URLField(default=None, null=True, blank=True)
    sample_file_size = models.IntegerField(default=0)

    tags = models.ManyToManyField(Tag)

    posted = models.BooleanField(default=False)
    weibo = models.OneToOneField("bot.Weibo", default=None, null=True, blank=True, on_delete=models.SET_NULL)

    uploader = models.ForeignKey("hub.Uploader", on_delete=models.SET_NULL, default=None, null=True);

    update_time = models.DateTimeField(auto_now=True)

    @property
    def media_url(self):
        return "{}{}.{}".format(SAKUGABOORU_DATA_URL, self.md5, self.ext)

    @property
    def preview_url(self):
        return "{}{}.{}".format(SAKUGABOORU_PREVIEW_URL,
                                self.md5,
                                SAKUGABOORU_PREVIEW_EXT)

    @property
    def sakugabooru_url(self):
        return "{}{}".format(SAKUGABOORU_POST, self.id)

    @property
    def file_name(self):
        return "{}.{}".format(self.md5, self.ext)

    @property
    def sample_file_name(self):
        return self.sample_url.split("/")[-1]

    @property
    def preview_file_name(self):
        return "{}.{}".format(self.md5, SAKUGABOORU_PREVIEW_EXT)

    @property
    def weibo_file_name(self):
        if self.ext in ANIMATED_MEDIA_EXTS:
            return "{}.{}".format(self.md5, "gif")
        return self.file_name


class UserProfile(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    edit_times = models.IntegerField(default=0)
    approved_times = models.IntegerField(default=0)
    node_count = models.IntegerField(default=0)

    remove_flag = models.BooleanField(default=False)


class LikeLog(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    snapshot = models.ForeignKey(TagSnapshot, on_delete=models.CASCADE)
    create_time = models.DateTimeField(auto_created=True)
