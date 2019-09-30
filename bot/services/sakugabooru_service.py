import logging
from datetime import datetime

from django.db import transaction
from pybooru import Moebooru
from pytz import utc

from bot.constants import SAKUGABOORU_BASE_URL
from hub.models import Post, Tag, Uploader

logger = logging.getLogger("bot.services.sakugabooru")


class SakugabooruService(object):
    BASE_URL = SAKUGABOORU_BASE_URL
    MAX_DEPTH = 11

    def __init__(self):
        self.client = Moebooru(site_url=self.BASE_URL)
        self.local_cache = dict()
        self.max_page = 1e9
        self.created_tags = list()

    def _save_post(self, post_dict):
        post, created = Post.objects.update_or_create(
            id=post_dict['id'],
            defaults={
                'source': post_dict['source'],
                'file_size': post_dict['file_size'],
                'is_shown': post_dict['is_shown_in_index'],
                'is_pending': post_dict['status'] == "pending",
                'md5': post_dict['md5'],
                'ext': post_dict['file_ext'],
                'created_at': datetime.fromtimestamp(int(post_dict['created_at']), tz=utc),
                'score': post_dict['score'],
                'rating': post_dict['rating'],
                'sample_url': post_dict['sample_url'],
                'sample_file_size': post_dict['sample_file_size']
            })
        tags = self.update_tags(post_dict['tags'].split(' '))
        with transaction.atomic():
            post.tags.clear()
            for tag in tags:
                post.tags.add(tag)
        post.uploader = self.update_uploader(post_dict['author'], post.is_pending, post.is_shown)
        post.save()
        logger.info("Post[{}] updated.".format(post.id))
        return post

    @staticmethod
    def update_uploader(author, is_pending, is_shown):
        uploader, created = Uploader.objects.get_or_create(name=author)
        if is_shown and not (is_pending or uploader.in_whitelist):
            uploader.in_whitelist = True
            uploader.save()
        return uploader

    def update_tag(self, tag):
        res = self.client.tag_list(name=tag.name)
        for tag_dict in res:
            if tag_dict['name'] == tag.name:
                if tag.type != tag_dict['type']:
                    tag.type = tag_dict['type']
                    tag.save()
                    logger.info("Tag[{}] type has been updated.".format(tag.name))
                break
        return tag

    def update_tags(self, tag_str_list, force_update=False):
        tags = list()
        for tag_str in tag_str_list:
            tag, created = Tag.objects.get_or_create(name=tag_str)

            if created or force_update:
                self.created_tags.append(tag)
                try:
                    self.update_tag(tag)
                except:
                    logger.exception("Update tag [] from sakugabooru failed.".format(tag.name))

            tags.append(tag)
        return tags

    def _get_post_dict_by_api(self, post_id):
        """
        get post_dict by post_id using api and save every accessed page to cache.
        :param post_id: Integer
        :return: success: post_dict; failed: None
        """
        limit = 100
        post_dict = self.local_cache.get(post_id, None)
        if post_dict:
            return post_dict
        page_stack = list()
        min_page = 1
        page_stack.append(min_page)
        max_page = self.max_page
        while page_stack and len(page_stack) <= self.MAX_DEPTH:
            res = self._get_posts_page(page=page_stack[-1], limit=limit)

            if not res:
                last_page = page_stack.pop()
                if last_page < self.max_page:
                    self.max_page = last_page
                if last_page < max_page:
                    max_page = last_page
                if len(page_stack) > 0:
                    page_stack.append((max_page + page_stack[-1]) // 2)
                    continue
                return None

            first_id = res[0]["id"]
            last_id = res[-1]["id"]

            logger.info("Posts Page[{}]: first[{}], last [{}]".format(page_stack[-1],
                                                                      first_id,
                                                                      last_id))

            if post_id > first_id:
                if page_stack[-1] <= 1:
                    return None

                next_page = max(page_stack[-1] + (-(post_id - first_id) // limit),
                                (min_page + page_stack[-1]) // 2)
                max_page = page_stack[-1]

                if next_page < 1:
                    next_page = 1

                page_stack.append(next_page)
            elif post_id < last_id:
                next_page = min(page_stack[-1] - (-(last_id - post_id) // limit),
                                (max_page + page_stack[-1]) // 2)
                min_page = page_stack[-1]
                if next_page in page_stack:
                    break
                if next_page > self.max_page:
                    next_page = (self.max_page + page_stack[-1]) // 2
                page_stack.append(next_page)
            else:
                return self.local_cache.get(post_id)

        return self.local_cache.get(post_id, None)

    def update_post(self, post_id):
        posts = self.update_posts(post_id)
        if posts:
            return posts[0]
        return None

    def update_posts(self, *post_ids):
        try:
            for post_id in post_ids:
                if post_id not in self.local_cache:
                    if not self._get_post_dict_by_api(post_id):
                        try:
                            post = Post.objects.get(id=post_id)
                            post.is_shown = False
                            post.is_pending = False
                            post.save()
                        except Post.DoesNotExist:
                            pass
        finally:
            for v in self.local_cache.values():
                self._save_post(v)
        return Post.objects.filter(id__in=post_ids)

    def _save_cache(self, res):
        for post_dict in res:
            self.local_cache[post_dict["id"]] = post_dict

    @staticmethod
    def _refresh_is_shown(page_res):
        if page_res:
            for post in Post.objects.filter(id__gte=page_res[-1]['id'], id__lte=page_res[0]['id']).exclude(
                    id__in=[x['id'] for x in page_res]):
                post.is_pending = False
                post.is_shown = False
                post.save()

    def _get_posts_page(self, page=1, limit=100):
        try:
            res = self.client.post_list(page=page, limit=limit)
            self._save_cache(res)
            self._refresh_is_shown(res)
            return res
        except:
            logger.exception("Failed to get posts page [{}] from sakugabooru with limit[{}].".format(page, limit))
            return dict()

    def update_posts_by_page(self, page=1, limit=100, escape_id=None):
        posts = list()
        logger.info("Getting posts page [{}] from sakugabooru with limit[{}].".format(page, limit))
        for post_dict in self._get_posts_page(page=page, limit=limit):
            if escape_id and post_dict["id"] <= escape_id:
                break
            post = self._save_post(post_dict)
            if post:
                posts.append(post)
        return posts
