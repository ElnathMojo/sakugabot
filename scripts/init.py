import argparse
import json
import os
from datetime import datetime

import django
import regex
from pytz import utc

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sakugabot.settings")
django.setup()
from scripts.attributes import META_ATTRIBUTES
from hub.models import Attribute, Tag, Uploader, Post
from bot.models import AccessToken, Weibo


def init_attributes():
    for attr in META_ATTRIBUTES:
        code = attr.pop("code")
        Attribute.objects.update_or_create(
            code=code,
            defaults=attr
        )


ABANDONED_TAGS = []
ABANDONED_TAGS_E = []


def _remove_space(name):
    if not name:
        return name
    pattern = regex.compile(r".*[\da-zA-Z]+.*")
    if not regex.match(pattern, name):
        if name.count(' ') == 1:
            return name.replace(' ', '')
    return name


def import_tags(tag_list):
    total = len(tag_list)
    last = 0
    for i, tag_dict in enumerate(tag_list):
        now = int(100 * i / total)
        if now > last:
            print("Tag Importing: {}%".format(now))
            last = now

        backup = tag_dict.copy()

        name = tag_dict.pop('name')
        type = tag_dict.pop('type')
        override_name = _remove_space(tag_dict.pop('override_name'))

        if type not in [x[0] for x in Tag.TYPE_CHOICES]:
            Uploader.objects.get_or_create(name=name, defaults={'override_name': override_name})
            continue

        tag, flag = Tag.objects.update_or_create(name=name,
                                                 defaults={
                                                     'override_name': override_name
                                                 })
        tag.type = type
        tag.save()  # prevent from triggering signal

        if not flag:
            ABANDONED_TAGS_E.append(backup)
            continue

        name_zh = tag_dict['name_zh']
        name_ja = tag_dict['name_ja'] = _remove_space(tag_dict['name_ja'])
        tag_dict = dict(x for x in tag_dict.items() if x[-1])
        if override_name:
            if type == Tag.ARTIST and name_ja and override_name != name_ja:
                ABANDONED_TAGS.append(backup)
                continue

            elif type == Tag.COPYRIGHT and name_zh and name_zh != override_name:
                ABANDONED_TAGS.append(backup)
                tag_dict.pop('name_ja')
                if tag_dict.get('bgm_sid'):
                    tag_dict.pop('bgm_sid')
        tag._detail.update(tag_dict)
        tag.save()


def import_posts(post_list):
    total = len(post_list)
    last = 0
    for i, post_dict in enumerate(post_list):
        now = int(100 * i / total)
        if now > last:
            print("Post Importing: {}%".format(now))
            last = now
        id = post_dict.pop('id')
        tag_str_list = post_dict.pop('tags')
        tags = Tag.objects.filter(name__in=tag_str_list)
        weibo_id = post_dict.pop('weibo_id')
        img_url = post_dict.pop('img_url')
        post_dict['created_at'] = datetime.utcfromtimestamp(post_dict['created_at'])
        weibo = None
        if weibo_id and img_url:
            weibo, dummy = Weibo.objects.get_or_create(weibo_id=weibo_id,
                                                       defaults={'img_url': img_url})

        if post_dict['is_shown'] is None:
            post_dict['is_shown'] = True
        if post_dict['is_pending'] is None:
            post_dict['is_pending'] = False
        if post_dict['score'] is None:
            post_dict['score'] = 0
        post_dict['posted'] = bool(weibo_id)
        post_dict['weibo'] = weibo

        post, flag = Post.objects.get_or_create(id=id,
                                                defaults=post_dict)
        if flag:
            post.tags.add(*tags)
        if post.weibo and weibo and post.weibo != weibo:
            try:
                Post.objects.get(weibo=weibo)
            except:
                weibo.delete()
                post.weibo = None
                print("delete weibo {}".format(weibo.id))
        else:
            post.weibo = weibo
        post.save()


def import_token(token_dict):
    AccessToken.objects.update_or_create(uid=token_dict['uid'],
                                         defaults={
                                             'access_token': token_dict['access_token'],
                                             'expires_at': datetime.fromtimestamp(
                                                 int(token_dict['expires_at']), tz=utc)})


def get_json(path):
    with open(path) as f:
        return json.load(f)


def import_old_data():
    for file, func in [('tags.json', import_tags),
                       ('posts.json', import_posts),
                       ('token.json', import_token)
                       ]:
        try:
            func(get_json(file))
        except FileNotFoundError:
            pass


def delete_existing_data():
    Tag.objects.all().delete()
    Post.objects.all().delete()
    Weibo.objects.all().delete()


parser = argparse.ArgumentParser(description='Init Data')

if __name__ == "__main__":
    args = parser.parse_args()
    init_attributes()
