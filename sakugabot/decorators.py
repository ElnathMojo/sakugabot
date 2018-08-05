from django.contrib import messages
from django.shortcuts import redirect
from ratelimit.decorators import ratelimit

from sakugabot.settings import LOGIN_RATE_LIMIT


def login_wrapper(login_func):
    @ratelimit(method='POST', key='post:X', rate=LOGIN_RATE_LIMIT)
    def admin_login(request, **kwargs):
        if getattr(request, 'limited', False):
            messages.error(request, 'Too many login attemps, please wait {}'.format(LOGIN_RATE_LIMIT.split('/')[-1]))
            return redirect(
                "{}?{}".format(request.path, request.GET.urlencode(safe='/')) if request.GET else request.path)
        else:
            return login_func(request, **kwargs)

    return admin_login
