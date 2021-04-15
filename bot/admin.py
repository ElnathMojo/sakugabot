from datetime import datetime

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.urls import path
from pytz import utc

from bot.models import AccessToken, Weibo
from bot.services.utils.weibo import Client
from hub.admin import object_link


@admin.register(AccessToken)
class AccessTokenAdmin(admin.ModelAdmin):
    list_display = ('uid', 'enable')
    list_filter = ('enable',)
    search_fields = ('uid',)

    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name

        my_urls = [
            path('obtain/', self.admin_site.admin_view(self.gen_token), name='%s_%s_obtain_token' % info)
        ]
        return my_urls + urls

    def gen_token(self, request):
        has_view_permission = self.has_view_permission(request)
        if not has_view_permission:
            raise PermissionDenied
        code = request.GET.get('code', None)
        weibo = Client(settings.WEIBO_API_KEY,
                       settings.WEIBO_API_SECRET,
                       settings.WEIBO_REDIRECT_URI)
        context = dict(
            self.admin_site.each_context(request),
            title="Obtain Token",
            has_view_permission=has_view_permission,
            opts=self.model._meta
        )

        if not code:
            context['authorize_url'] = weibo.authorize_url
            return TemplateResponse(request, "gen_token.html", context)

        try:
            weibo.set_code(code)
            ac, dummy = AccessToken.objects.update_or_create(uid=weibo.uid,
                                                             defaults={
                                                                 'access_token': weibo.access_token,
                                                                 'expires_at': datetime.fromtimestamp(
                                                                     int(weibo.expires_at), tz=utc)})

            return self.change_view(
                request, ac.pk, ''
            )
        except Exception as e:
            context['error'] = str(e)
            return TemplateResponse(request, "gen_token.html", context)


@admin.register(Weibo)
class WeiboAdmin(admin.ModelAdmin):
    list_display = ('weibo_id', 'img_url', 'create_time', object_link('uid'), object_link('post'))
    search_fields = ('weibo_id', 'img_url', 'uid__uid')
