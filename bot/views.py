import collections
import os

import regex
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from rest_framework import status, serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from rest_framework.views import APIView

from api.permissions import IsAdminUser


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
        print([regex.escape(params['filter'])])
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


@user_passes_test(lambda u: u.is_superuser)
@api_view()
def test(request):
    pass
    return Response({"message": "Hello, world!"})
