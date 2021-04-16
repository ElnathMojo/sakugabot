import logging
from datetime import datetime

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.admin.utils import unquote
from django.contrib.auth.admin import sensitive_post_parameters_m
from django.contrib.auth.hashers import mask_hash
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import escape
from django.utils.translation import gettext, gettext_lazy as _
from pytz import utc

from bot.models import Weibo, Credential
from bot.services.utils.weibo import Client
from bot.services.utils.weiboV2 import WeiboAuthClient
from hub.admin import object_link

logger = logging.getLogger('bot.admin')

@admin.register(Weibo)
class WeiboAdmin(admin.ModelAdmin):
    list_display = ('weibo_id', 'img_url', 'create_time', object_link('uid'), object_link('post'))
    search_fields = ('weibo_id', 'img_url', 'uid__uid')


class CredentialCreationForm(forms.ModelForm):
    class Meta:
        model = Credential
        fields = ("uid", "account",)


class ReadOnlyPasswordHashWidget(forms.Widget):
    template_name = 'auth/widgets/read_only_password_hash.html'
    read_only = True

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        summary = []
        if not value:
            summary.append({'label': gettext("No password set.")})
        else:
            summary.append({'label': gettext(_('hash')), 'value': mask_hash(value)})
        context['summary'] = summary
        return context


class ReadOnlyPasswordHashField(forms.Field):
    widget = ReadOnlyPasswordHashWidget

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault('disabled', True)
        super().__init__(*args, **kwargs)


class CredentialChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label=_("Password"),
        help_text=_(
            'Raw passwords are not stored, so there is no way to see this '
            'user’s password, but you can change the password using '
            '<a href="{}">this form</a>.'
        ),
    )

    class Meta:
        model = Credential
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        password = self.fields.get('password')
        if password:
            password.help_text = password.help_text.format('../password/')


class CredentialPasswordChangeForm(forms.Form):
    required_css_class = 'required'
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'autofocus': True}),
        strip=True
    )

    def __init__(self, credential, *args, **kwargs):
        self.credential = credential
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        """Save the new password."""
        password = self.cleaned_data["password"]
        self.credential.set_password(password)
        if commit:
            self.credential.save()
        return self.credential

    @property
    def changed_data(self):
        data = super().changed_data
        for name in self.fields:
            if name not in data:
                return []
        return ['password']


class CredentialCodeForm(forms.Form):
    code = forms.CharField(max_length=6)


@admin.register(Credential)
class CredentialAdmin(admin.ModelAdmin):
    change_credential_password_template = 'credential_change_password.html'
    verify_credential_code_template = 'credential_verify_code.html'
    form = CredentialChangeForm
    add_form = CredentialCreationForm
    change_password_form = CredentialPasswordChangeForm
    code_form = CredentialCodeForm
    list_display = ('uid', 'account', 'enable')
    list_filter = ('enable',)
    search_fields = ('uid', 'account',)
    ordering = ('uid',)

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
            ac, dummy = Credential.objects.update_or_create(uid=weibo.uid,
                                                             defaults={
                                                                 'account': weibo.uid,
                                                                 'access_token': weibo.access_token,
                                                                 'expires_at': datetime.fromtimestamp(
                                                                     int(weibo.expires_at), tz=utc)})

            return self.change_view(
                request, ac.pk, ''
            )
        except Exception as e:
            context['error'] = str(e)
            return TemplateResponse(request, "gen_token.html", context)

    def get_form(self, request, obj=None, **kwargs):
        defaults = {}
        if obj is None:
            defaults['form'] = self.add_form
        defaults.update(kwargs)
        return super().get_form(request, obj, **defaults)

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        return [
                   path(
                       '<id>/password/',
                       self.admin_site.admin_view(self.credential_change_password),
                       name='%s_%s_password_change' % info,
                   ),
                   path(
                       '<id>/verify/',
                       self.admin_site.admin_view(self.credential_verify),
                       name='%s_%s_verify' % info,
                   ),
                   path('obtain/', self.admin_site.admin_view(self.gen_token), name='%s_%s_obtain_token' % info),
               ] + super().get_urls()

    def credential_verify(self, request, id, form_url=''):
        credential = self.get_object(request, unquote(id))
        if not self.has_change_permission(request, credential):
            raise PermissionDenied
        info = request.session.get(f"credential_{credential.pk}", None)
        if credential is None or info is None:
            raise Http404(_('%(name)s object with primary key %(key)r does not exist.') % {
                'name': self.model._meta.verbose_name,
                'key': escape(id),
            })
        if request.method == 'POST':
            form = self.code_form(request.POST)
            if form.is_valid():
                request.session.pop(f"credential_{credential.pk}")
                client = WeiboAuthClient(credential.aid)
                if credential.aid != client.aid:
                    credential.aid = client.aid
                    credential.save()
                status, res = client.check(form.cleaned_data['code'], info)
                if status == 0:
                    credential.gsid = res.get("gsid")
                    credential.raw_credentials = res
                    credential.save()
                    msg = 'Credential updated successfully.'
                    messages.success(request, msg)
                    return HttpResponseRedirect(
                        reverse(
                            '%s:%s_%s_change' % (
                                self.admin_site.name,
                                credential._meta.app_label,
                                credential._meta.model_name,
                            ),
                            args=(credential.pk,),
                        )
                    )
            msg = 'Credential updated failed.'
            messages.success(request, msg)
            return HttpResponseRedirect(
                reverse(
                    '%s:%s_%s_change' % (
                        self.admin_site.name,
                        credential._meta.app_label,
                        credential._meta.model_name,
                    ),
                    args=(credential.pk,),
                )
            )
        form = self.code_form()
        fieldsets = [(None, {'fields': list(form.base_fields)})]
        adminForm = admin.helpers.AdminForm(form, fieldsets, {})

        context = {
            'title': _('Change password: %s') % escape(credential.account),
            'adminForm': adminForm,
            'form_url': form_url,
            'form': form,
            'is_popup': (IS_POPUP_VAR in request.POST or
                         IS_POPUP_VAR in request.GET),
            'add': True,
            'change': False,
            'has_delete_permission': False,
            'has_change_permission': True,
            'has_absolute_url': False,
            'opts': self.model._meta,
            'original': credential,
            'save_as': False,
            'show_save': True,
            **self.admin_site.each_context(request),
        }

        request.current_app = self.admin_site.name

        return TemplateResponse(
            request,
            self.verify_credential_code_template,
            context,
        )

    @sensitive_post_parameters_m
    def credential_change_password(self, request, id, form_url=''):
        credential = self.get_object(request, unquote(id))
        if not self.has_change_permission(request, credential):
            raise PermissionDenied
        if credential is None:
            raise Http404(_('%(name)s object with primary key %(key)r does not exist.') % {
                'name': self.model._meta.verbose_name,
                'key': escape(id),
            })
        if request.method == 'POST':
            form = self.change_password_form(credential, request.POST)

            if form.is_valid():
                form.save()
                change_message = self.construct_change_message(request, form, None)
                self.log_change(request, credential, change_message)
                try:
                    client = WeiboAuthClient(credential.aid)
                    if credential.aid != client.aid:
                        credential.aid = client.aid
                        credential.save()
                    status_code, res = client.login_with_encrypt_password(
                        credential.account,
                        credential.password,
                        credential.login_s
                    )
                    if status_code == 0:
                        credential.gsid = res.get("gsid")
                        credential.raw_credentials = res
                        credential.save()
                        msg = gettext('Password changed successfully.')
                        messages.success(request, msg)
                        return HttpResponseRedirect(
                            reverse(
                                '%s:%s_%s_change' % (
                                    self.admin_site.name,
                                    credential._meta.app_label,
                                    credential._meta.model_name,
                                ),
                                args=(credential.pk,),
                            )
                        )
                    elif status_code > 0:
                        request.session[f"credential_{credential.pk}"] = res
                        return HttpResponseRedirect(
                            reverse(
                                '%s:%s_%s_verify' % (
                                    self.admin_site.name,
                                    credential._meta.app_label,
                                    credential._meta.model_name,
                                ),
                                args=(credential.pk,),
                            )
                        )
                except Exception as ignored:
                    logger.error(exc_info=True, stack_info=True)
                msg = f"{gettext('Password changed successfully.')} But update gsid failed."
                messages.success(request, msg)
                return HttpResponseRedirect(
                    reverse(
                        '%s:%s_%s_change' % (
                            self.admin_site.name,
                            credential._meta.app_label,
                            credential._meta.model_name,
                        ),
                        args=(credential.pk,),
                    )
                )
        else:
            form = self.change_password_form(credential)

        fieldsets = [(None, {'fields': list(form.base_fields)})]
        adminForm = admin.helpers.AdminForm(form, fieldsets, {})

        context = {
            'title': _('Change password: %s') % escape(credential.account),
            'adminForm': adminForm,
            'form_url': form_url,
            'form': form,
            'is_popup': (IS_POPUP_VAR in request.POST or
                         IS_POPUP_VAR in request.GET),
            'add': True,
            'change': False,
            'has_delete_permission': False,
            'has_change_permission': True,
            'has_absolute_url': False,
            'opts': self.model._meta,
            'original': credential,
            'save_as': False,
            'show_save': True,
            **self.admin_site.each_context(request),
        }

        request.current_app = self.admin_site.name

        return TemplateResponse(
            request,
            self.change_credential_password_template,
            context,
        )
