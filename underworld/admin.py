from django.contrib import admin

from hub.admin import object_link
from underworld.models import IP, AccessLog
from underworld.tasks import get_ip_info


class UnderWorldBaseAdmin(admin.ModelAdmin):
    def default_permission(self, request):
        if request.user.id == 1 and request.user.is_superuser:
            return True
        return False

    def has_view_permission(self, request, obj=None):
        return self.default_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.default_permission(request)

    def has_add_permission(self, request):
        return self.default_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.default_permission(request)


@admin.register(IP)
class IPAdmin(UnderWorldBaseAdmin):
    list_display = (
        'address', 'country', 'country_code', 'region', 'region_name', 'city', 'zip', 'lat', 'lon', 'timezone', 'isp',
        'org', '_as')
    search_fields = (
        'address', 'country', 'country_code', 'region', 'region_name', 'city', 'zip', 'lat', 'lon', 'timezone', 'isp',
        'org', '_as')
    actions = ['update_info']

    def update_info(self, request, queryset):
        get_ip_info.delay(*[x.address for x in queryset])

    update_info.short_description = "Update Selected IPs' Information"


@admin.register(AccessLog)
class AccessLogAdmin(UnderWorldBaseAdmin):
    date_hierarchy = 'create_time'

    list_display = (
        'create_time', object_link('remote_addr'), object_link('client_addr'), object_link('user'), 'request_method',
        'request_path', 'status', 'body_bytes_sent', 'http_referer', 'http_user_agent', 'forwarded_for')
    search_fields = (
        'create_time', 'remote_addr', 'client_addr', 'user', 'request_method', 'request_path', 'status',
        'body_bytes_sent', 'http_referer', 'http_user_agent', 'forwarded_for')
    list_filter = ('user', 'request_method')

    actions = ['clean_logs_before']

    def clean_logs_before(self, request, queryset):
        AccessLog.objects.filter(create_time__lte=queryset.order_by('-create_time')[0].create_time).delete()

    clean_logs_before.short_description = "Clean Logs Before Those"
