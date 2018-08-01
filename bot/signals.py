from django.db.models.signals import post_save
from django.dispatch import receiver

from bot.tasks import update_tags_info_task
from hub.models import Tag


@receiver(post_save, sender=Tag)
def get_tag_info(sender, instance=None, created=False, **kwargs):
    if created and instance.type in (Tag.COPYRIGHT, Tag.ARTIST):
        update_tags_info_task.delay(instance.pk)
