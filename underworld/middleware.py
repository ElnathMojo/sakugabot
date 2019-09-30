from django.contrib.auth.models import AnonymousUser

from underworld.models import AccessLog, IP
from underworld.tasks import get_ip_info


class AccessLogMiddleware:
    def __init__(self, get_response=None):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            user = getattr(request, 'user', AnonymousUser())

            remote_addr = client_addr = None
            forwarded_for = []
            try:
                remote_addr_raw = request.META.get('HTTP_X_REAL_IP', None)
                forwarded_for_raw = request.META.get('HTTP_X_FORWARDED_FOR', None)
                forwarded_for = [ip.strip() for ip in forwarded_for_raw.split(',')] if forwarded_for_raw else list()
                client_addr_raw = forwarded_for[0] if forwarded_for else None

                if remote_addr_raw:
                    remote_addr, created = IP.objects.get_or_create(address=remote_addr_raw)
                    if created:
                        get_ip_info.delay(remote_addr.address)

                if client_addr_raw:
                    client_addr, created = IP.objects.get_or_create(address=client_addr_raw)
                    if created:
                        get_ip_info.delay(client_addr.address)
            finally:
                AccessLog.objects.create(
                    remote_addr=remote_addr,
                    client_addr=client_addr,
                    user=None if user.is_anonymous else user,
                    request_method=request.method,
                    request_path=request.path,
                    status=response.status_code,
                    body_bytes_sent=len(response.content),
                    http_referer=request.META.get('HTTP_REFERER', None),
                    http_user_agent=request.META.get('HTTP_USER_AGENT', None),
                    forwarded_for=forwarded_for
                )
        finally:
            return response
