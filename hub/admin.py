from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from bot.tasks import update_tags_info_task, update_posts_task
from hub.models import Post, Tag, TagSnapshot, Attribute, Node, TagSnapshotNodeRelation, Uploader


class TranslationFilter(admin.SimpleListFilter):
    title = _('translation')

    parameter_name = 'translation'

    def lookups(self, request, model_admin):
        return (
            ('exists', _('exists')),
            ('not_exists', _('not exists')),
            ('override_only', _('override only')),
            ('all_empty', _('all empty'))
        )

    def queryset(self, request, queryset):
        if self.value() == 'exists':
            return queryset.filter(Q(override_name__isnull=False) | Q(_detail__name_zh__isnull=False) | Q(
                _detail__name_main__isnull=False) | (Q(type=Tag.ARTIST) & Q(_detail__name_ja__isnull=False)))
        if self.value() == 'not_exists':
            return queryset.filter(~(Q(override_name__isnull=False) | Q(_detail__name_zh__isnull=False) | Q(
                _detail__name_main__isnull=False) | (Q(type=Tag.ARTIST) & Q(_detail__name_ja__isnull=False))))
        if self.value() == 'override_only':
            return queryset.filter(_detail={}, override_name__isnull=False)
        if self.value() == 'all_empty':
            return queryset.filter(_detail={}, override_name__isnull=True)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    fields = (
        'name', 'override_name', 'deletion_flag', 'is_editable', '_detail', 'order_of_keys', 'like_count')
    list_display = ('name', 'weibo_name', 'type')
    list_filter = ('type', TranslationFilter)
    search_fields = ('name',)
    readonly_fields = ('like_count', 'order_of_keys', 'post_set', '_detail')

    actions = ['update_info']

    def update_info(self, request, queryset):
        update_tags_info_task.delay(*[x.pk for x in queryset], update_tag_type=True)

    update_info.short_description = _("Update Selected Tags' Information")


class SkippedFilter(admin.SimpleListFilter):
    title = _('Skipped')

    parameter_name = 'skipped'

    def lookups(self, request, model_admin):
        return (
            ('skipped', _('skipped')),
            ('normal', _('normal')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'skipped':
            return queryset.filter(Q(posted=True) & Q(weibo__isnull=True))
        if self.value() == 'normal':
            return queryset.filter(~(Q(posted=True) & Q(weibo__isnull=True)))


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'post_tags', 'source', 'uploader',
                    'md5', 'ext', 'created_at', 'rating',
                    'weibo_id')
    list_filter = ('posted', 'ext', 'rating', SkippedFilter)
    search_fields = ('id', 'md5', 'uploader')

    actions = ['update_info']

    def post_tags(self, obj):
        return " ".join([tag.name for tag in obj.tags.all()])

    post_tags.short_description = 'Tags'

    def weibo_id(self, obj):
        try:
            return format_html('<a href="{}">{}</a>',
                               obj.weibo.img_url,
                               obj.weibo.weibo_id)
        except:
            return 'None'

    weibo_id.short_description = 'Weibo'

    def update_info(self, request, queryset):
        update_posts_task.delay(*[x.pk for x in queryset])

    update_info.short_description = _("Update Selected Posts' Information")


@admin.register(TagSnapshot, Node, TagSnapshotNodeRelation)
class KangKangAdmin(admin.ModelAdmin):
    def default_permission(self, request):
        if request.user.id <= 3:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        return self.default_permission(request)

    def has_add_permission(self, request):
        return self.default_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.default_permission(request)


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    readonly_fields = ('code', 'type', 'related_types')

    def has_delete_permission(self, request, obj=None):
        if request.user.id <= 1:
            return True
        return False


@admin.register(Uploader)
class UploaderAdmin(admin.ModelAdmin):
    list_display = ('name', 'override_name')
