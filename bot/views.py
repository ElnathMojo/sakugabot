import os

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from rest_framework import permissions, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from rest_framework.views import APIView


class ShowLog(APIView):
    """
    Query Params：
        n: number of lines to return.
        log: name of the log.
        filter: if set, only return lines that contain filter.
    """
    permission_classes = (permissions.IsAdminUser,)

    def get(self, request, format=None):
        try:
            n = int(request.query_params.get('n', 100))
            file = request.query_params.get('log', 'bot.log')
            keyword = request.query_params.get('filter', None)
            output = list()
            with open(os.path.join(settings.BASE_DIR, 'log/{}'.format(file)), 'r') as f:
                for line in f.readlines():
                    if keyword and keyword in line or not keyword:
                        output.append(line.strip())

            return Response(output[-n:])
        except Exception as e:
            return Response(str(e), status=status.HTTP_400_BAD_REQUEST)


@user_passes_test(lambda u: u.is_superuser)
@api_view()
def test(request):
    pass
    return Response({"message": "Hello, world!"})
