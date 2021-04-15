from collections import OrderedDict
from functools import partial

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import DELETION, LogEntry
from django.contrib.admin.utils import flatten_fieldsets, quote
from django.core.exceptions import FieldError
from django.core.validators import RegexValidator
from django.db.models import Q
from django import forms
from django.forms import modelform_factory
from django.forms.models import modelform_defines_fields
from django.urls import reverse
from django.utils.html import format_html, escape
from django.utils.translation import gettext_lazy as _

from bot.tasks import update_tags_info_task, update_posts_task, post_weibo_task
from hub.models import Post, Tag, TagSnapshot, Attribute, Node, TagSnapshotNodeRelation, Uploader


def object_link(field, short_description=None, admin_order_field=None):
    def _object_link(obj):
        field_obj = getattr(obj, field)
        if field_obj:
            link = format_html(u'<a href="%s">%s</a>' % (
                reverse('admin:%s_%s_change' % (field_obj._meta.app_label, field_obj._meta.model_name),
                        args=[quote(getattr(obj, field).pk)]),
                escape(getattr(obj, field)),
            ))
        else:
            link = escape(field_obj)
        return link

    _object_link.admin_order_field = admin_order_field if admin_order_field else field
    _object_link.short_description = short_description if short_description else field
    return _object_link


class TranslationFilter(admin.SimpleListFilter):
    title = _('translation')

    parameter_name = 'translation'

    def lookups(self, request, model_admin):
        return (
            ('exists', _('exists')),
            ('not_exists', _('not exists')),
            ('has_override', _('has override name'))
        )

    def queryset(self, request, queryset):
        if self.value() == 'exists':
            return queryset.filter(Q(override_name__isnull=False) | Q(_detail__name_zh__isnull=False) | Q(
                _detail__name_main__isnull=False) | (Q(type=Tag.ARTIST) & Q(_detail__name_ja__isnull=False)))
        if self.value() == 'not_exists':
            return queryset.filter(~(Q(override_name__isnull=False) | Q(_detail__name_zh__isnull=False) | Q(
                _detail__name_main__isnull=False) | (Q(type=Tag.ARTIST) & Q(_detail__name_ja__isnull=False))))
        if self.value() == 'has_override':
            return queryset.filter(override_name__isnull=False)


class TagForm(forms.ModelForm):
    def __init__(self, *arg, **kwargs):
        super(TagForm, self).__init__(*arg, **kwargs)
        for name, field in self.fields.items():
            if name.startswith('_detail__'):
                value = self.instance._detail.get(name.replace('_detail__', ''), None)
                if value:
                    self.initial[name] = value

    def save(self, commit=True):
        for key, value in self.cleaned_data.items():
            if key.startswith('_detail__'):
                attr = key.replace('_detail__', '')
                if value or value == 0:
                    try:
                        self.instance.save_to_detail(attr, value)
                        continue
                    except AttributeError:
                        pass
                self.instance._detail.pop(attr, None)
        return super(TagForm, self).save(commit)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    form = TagForm
    fields = (
        'name', 'type', 'override_name', 'deletion_flag', 'is_editable', 'order_of_keys', 'like_count')
    list_display = ('name', 'type', 'names', 'override_name', 'weibo_name')
    list_filter = ('type', TranslationFilter)
    search_fields = ['name', 'override_name'] + ['_detail__{}'.format(attr) for attr in
                                                 ['name_{}'.format(lan) for lan in settings.DEFAULT_LANGUAGES] + [
                                                     'name_main']]
    readonly_fields = ('name', 'type', 'like_count', 'override_name')
    actions = ['update_info', 'update_info_overwrite', 'update_type']

    def view_on_site(self, obj):
        url = reverse('api:tag-detail', kwargs={'pk': obj.pk})
        return url

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            (None, {
                'fields': self.get_fields(request, obj) if obj else ('name', 'type')
            })]
        if obj:
            fieldsets.append(
                ('Tag Detail', {
                    'classes': ('wide', 'extrapretty'),
                    'fields': ['_detail__%s' % x.code for x in
                               Attribute.objects.filter(related_types__contains=[obj.type]).order_by('order')],
                }))

        return fieldsets

    def get_form(self, request, obj=None, change=False, **kwargs):
        """
        Return a Form class for use in the admin add view. This is used by
        add_view and change_view.
        """
        if 'fields' in kwargs:
            fields = kwargs.pop('fields')
        else:
            fields = flatten_fieldsets(self.get_fieldsets(request, obj))
        excluded = self.get_exclude(request, obj)
        exclude = [] if excluded is None else list(excluded)
        readonly_fields = self.get_readonly_fields(request, obj)
        exclude.extend(readonly_fields)
        # Exclude all fields if it's a change form and the user doesn't have
        # the change permission.
        if change and hasattr(request, 'user') and not self.has_change_permission(request, obj):
            exclude.extend(fields)
        if excluded is None and hasattr(self.form, '_meta') and self.form._meta.exclude:
            # Take the custom ModelForm's Meta.exclude into account only if the
            # ModelAdmin doesn't define its own.
            exclude.extend(self.form._meta.exclude)
        # if exclude is an empty list we pass None to be consistent with the
        # default on modelform_factory
        exclude = exclude or None

        # Remove declared form fields which are in readonly_fields.
        new_attrs = OrderedDict.fromkeys(
            f for f in readonly_fields
            if f in self.form.declared_fields
        )
        # MediaDefiningClass
        if obj:
            detail_attrs = dict()
            for attr in Attribute.objects.filter(related_types__contains=[obj.type]):
                widget = forms.Textarea if attr.code == "description" else attr.form_field_class.widget
                detail_attrs['_detail__%s' % attr.code] = attr.form_field_class(label=attr.name,
                                                                                required=False,
                                                                                widget=widget(attrs={
                                                                                    'class': 'vTextField'}),
                                                                                help_text=attr.code,
                                                                                validators=[
                                                                                    RegexValidator(
                                                                                        attr.regex)] if attr.regex \
                                                                                    else [])
            new_attrs.update(detail_attrs)
        form = type(self.form.__name__, (self.form,), new_attrs)

        defaults = {
            'form': form,
            'fields': fields,
            'exclude': exclude,
            'formfield_callback': partial(self.formfield_for_dbfield, request=request),
            **kwargs,
        }

        if defaults['fields'] is None and not modelform_defines_fields(defaults['form']):
            defaults['fields'] = forms.ALL_FIELDS

        try:
            return modelform_factory(self.model, **defaults)
        except FieldError as e:
            raise FieldError(
                '%s. Check fields/fieldsets/exclude attributes of class %s.'
                % (e, self.__class__.__name__)
            )

    def save_model(self, request, obj, form, change):
        obj.save(editor=request.user)

    def get_actions(self, request):
        actions = super(TagAdmin, self).get_actions(request)
        if not request.user.is_superuser:
            for key in ['update_info_overwrite', 'update_info']:
                actions.pop(key, None)
        return actions

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return []
        if obj is None:
            return 'like_count', 'override_name'
        return self.readonly_fields

    def update_type(self, request, queryset):
        try:
            from bot.services.sakugabooru_service import SakugabooruService
            SakugabooruService().update_tags([tag.name for tag in queryset], force_update=True)
        finally:
            pass

    update_type.short_description = _("Update Selected Tags' Type From Sakugabooru")

    def update_info(self, request, queryset):
        update_tags_info_task.delay(*[x.pk for x in queryset], update_tag_type=True)

    update_info.short_description = _("Update Selected Tags' Information")

    def update_info_overwrite(self, request, queryset):
        update_tags_info_task.delay(*[x.pk for x in queryset], update_tag_type=True, overwrite=True)

    update_info_overwrite.short_description = _("Update Selected Tags' Information(Overwrite)")


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
            return queryset.filter(Q(posted=True) & Q(weibo__isnull=True) & Q(is_shown=True))
        if self.value() == 'normal':
            return queryset.filter(~(Q(posted=True) & Q(weibo__isnull=True) & Q(is_shown=True)))


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'post_tags', 'source', object_link('uploader'),
                    'md5', 'ext', 'created_at', 'rating',
                    'weibo_id')
    raw_id_fields = ("tags", "weibo", "uploader")
    list_filter = ('posted', 'ext', 'rating', SkippedFilter)
    search_fields = ('id', 'md5', 'uploader__name')

    actions = ['update_info', 'post_weibo']

    def view_on_site(self, obj):
        url = reverse('api:post-detail', kwargs={'pk': obj.pk})
        return url

    def post_tags(self, obj):
        return " ".join([tag.name for tag in obj.tags.all()])

    post_tags.short_description = 'Tags'

    def weibo_id(self, obj):
        try:
            return format_html('<a href="{}">{}</a> <a href="{}">img</a>',
                               obj.weibo.weibo_url,
                               obj.weibo.weibo_id,
                               obj.weibo.img_url)
        except:
            return 'None'

    weibo_id.short_description = _('Weibo')

    def update_info(self, request, queryset):
        update_posts_task.delay(*[x.pk for x in queryset])

    update_info.short_description = _("Update Selected Posts' Information")

    def post_weibo(self, request, queryset):
        post_weibo_task.delay(*[x.pk for x in queryset.filter(weibo__isnull=True)])

    post_weibo.short_description = _("Post Selected Posts to Weibo")


class UserFilter(admin.SimpleListFilter):
    title = _('User Type')

    parameter_name = 'user_type'

    def lookups(self, request, model_admin):
        return (
            ('human', _('human')),
            ('system', _('system'))
        )

    def queryset(self, request, queryset):
        if self.value() == 'human':
            return queryset.filter(_user__isnull=False)
        if self.value() == 'system':
            return queryset.filter(_user__isnull=True)


class KangKangAdmin(admin.ModelAdmin):
    def default_permission(self, request):
        if request.user.id <= 3 and request.user.is_superuser:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        return self.default_permission(request)

    def has_add_permission(self, request):
        return self.default_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.default_permission(request)


@admin.register(TagSnapshot)
class TagHistoryAdmin(KangKangAdmin):
    date_hierarchy = 'update_time'

    list_display = ('update_time', 'id', object_link('tag'), '_user', 'note', 'hash', 'create_time')
    list_filter = (UserFilter,)
    search_fields = ('_user__username', 'tag__name', 'hash')

    def view_on_site(self, obj):
        url = reverse('api:tagsnapshot-detail', kwargs={'pk': obj.pk})
        return url


@admin.register(Node)
class NodeAdmin(KangKangAdmin):
    list_display = ('id', object_link('attribute'), '_value', 'length', 'hash')
    search_fields = ('id', 'attribute__code', '_value', 'hash')


@admin.register(TagSnapshotNodeRelation)
class TagSnapshotNodeRelationAdmin(KangKangAdmin):
    date_hierarchy = 'tag_snapshot__update_time'
    list_display = ('id', object_link('tag_snapshot'), object_link('node'), 'order')
    search_fields = ('tag_snapshot__id', 'node__id')


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ('code', 'type', 'name', 'regex', 'format', 'order', 'related_types')
    list_filter = ('type',)
    readonly_fields = ('code', 'type', 'related_types')
    search_fields = ('code', 'type')
    actions = ['init_attributes']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields
        else:
            return []

    def init_attributes(self, request, queryset):
        from scripts.init import init_attributes
        init_attributes()

    init_attributes.short_description = _("Init Attributes")

    def has_delete_permission(self, request, obj=None):
        if request.user.id <= 1:
            return True
        return False


@admin.register(Uploader)
class UploaderAdmin(admin.ModelAdmin):
    list_display = ('name', 'override_name', 'in_blacklist', 'in_whitelist')
    search_fields = ('name', 'override_name')
    list_filter = [
        'in_blacklist',
        'in_whitelist'
    ]
    actions = ['add_to_blacklist', 'remove_from_blacklist', 'refresh_whitelist']

    def add_to_blacklist(self, request, queryset):
        queryset.update(in_blacklist=True)

    add_to_blacklist.short_description = _("Add to Blacklist")

    def remove_from_blacklist(self, request, queryset):
        queryset.update(in_blacklist=False)

    remove_from_blacklist.short_description = _("Remove from Blacklist")

    def refresh_whitelist(self, request, queryset):
        queryset.update(in_whitelist=False)
        queryset.filter(post__is_pending=False, post__is_shown=True).update(in_whitelist=True)

    refresh_whitelist.short_description = _("Refresh Whitelist")


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    date_hierarchy = 'action_time'

    readonly_fields = [f.name for f in LogEntry._meta.get_fields()]

    list_filter = [
        'user',
        'content_type',
        'action_flag'
    ]

    search_fields = [
        'object_repr',
        'change_message',
        'user'
    ]

    list_display = [
        'action_time',
        'user',
        'content_type',
        'object_link',
        'action_flag',
        'change_message',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and request.method != 'POST'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and request.user.id == 1

    def object_link(self, obj):
        if obj.action_flag == DELETION:
            link = escape(obj.object_repr)
        else:
            ct = obj.content_type
            link = format_html(u'<a href="%s">%s</a>' % (
                reverse('admin:%s_%s_change' % (ct.app_label, ct.model), args=[quote(obj.object_id)]),
                escape(obj.object_repr),
            ))
        return link

    object_link.admin_order_field = 'object_repr'
    object_link.short_description = u'object'

    def get_queryset(self, request):
        return super(LogEntryAdmin, self).get_queryset(request).prefetch_related('content_type')
