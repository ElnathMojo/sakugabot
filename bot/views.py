import collections
import os

import regex
from PIL import Image
from django.conf import settings
from django.contrib.admin import site
from django.contrib.auth.decorators import user_passes_test
from django.template.response import TemplateResponse
from pyzbar.pyzbar import decode
from rest_framework import status, serializers
from rest_framework.decorators import api_view
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdminUser
from bot.models import Credential
from bot.services.utils.weiboV2 import WeiboAuthClient, CookieExpiredException


class QRCodeSerializer(serializers.Serializer):
    file = serializers.ImageField()

    def validate(self, attrs):
        data = super().validate(attrs)
        with Image.open(data['file']) as img:
            d = decode(img)
            if not d or len(d) <= 0:
                raise serializers.ValidationError("Can''t find QR Code in this image.")
            url = d[0].data.decode()
            if not url:
                raise serializers.ValidationError("Can''t find QR Code in this image.")
            data['url'] = url
        return data


class ScanQRCode(APIView):
    permission_classes = (IsAdminUser,)
    parser_classes = [FormParser, MultiPartParser]

    def post(self, request, format=None):
        print(request.data)
        print(request.FILES)
        print(request.POST)
        s = QRCodeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        url = s.validated_data.get('url')
        credential = Credential.objects.filter(enable=True).order_by('expires_at').last()
        cookies = credential.raw_credentials.get("cookie", {}).get("cookie", {})
        if not cookies and not credential.aid:
            Response("No valid Credential.", status=status.HTTP_404_NOT_FOUND)
        client = WeiboAuthClient(credential.aid)
        try:
            if not cookies:
                raise CookieExpiredException
            client.scan(url, cookies)
            return Response({"msg": "Success!"})
        except CookieExpiredException:
            try:
                code, res = client.login_with_gsid(credential.uid, credential.gsid)
            except:
                return Response({"msg": "Failed to update credential"}, status.HTTP_400_BAD_REQUEST)
            if code != 0:
                return Response({"msg": "Failed to update credential"}, status.HTTP_400_BAD_REQUEST)
            credential.gsid = res.get("gsid")
            credential.raw_credentials = res
            credential.save()
            cookies = credential.raw_credentials.get("cookie", {}).get("cookie", {})
        try:
            client.scan(url, cookies)
            return Response({"msg": "Success!"})
        except:
            return Response({"msg": "Failed to scan QR Code."}, status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        context = {
            "title": "Scan QR Code",
            "serializer": QRCodeSerializer(),
            **site.each_context(request)
        }
        return TemplateResponse(
            request,
            'scan_qr_code.html',
            context,
        )


class LogViewParamsSerializer(serializers.Serializer):
    n = serializers.IntegerField(default=100)
    file = serializers.CharField(default='bot.log')
    start = serializers.IntegerField(default=0)
    end = serializers.IntegerField(default=1e16)
    type = serializers.ChoiceField(choices=('tail', 'head'), default='tail')
    filter = serializers.CharField(default='')


class ShowLog(APIView):
    """
    Query Params：
        n: number of lines to return.
        log: name of the log.
        filter: if set, only return lines that contain filter.
        start: start line number
        end: end line number
        type: tail or head. default: tail
    """
    permission_classes = (IsAdminUser,)

    def get(self, request, format=None):

        s = LogViewParamsSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        params = s.validated_data
        try:
            output = list()
            with open(os.path.join(settings.BASE_DIR, 'log/{}'.format(params['file'])), 'r') as f:
                for no, line in enumerate(f.readlines()):
                    if params['start'] <= no <= params['end']:
                        if regex.search(regex.compile(params['filter']), line):
                            output.append((no, line.strip()))

            return Response(collections.OrderedDict(output[-params['n']:] if params['type'] == 'tail' else
                                                    output[:params['n']]))
        except Exception as e:
            return Response(str(e), status=status.HTTP_400_BAD_REQUEST)


@user_passes_test(lambda u: u.is_superuser, login_url="admin:login")
@api_view()
def test(request):
    pass
    return Response({"message": "Hello, world!"})
