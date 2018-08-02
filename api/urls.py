from django.conf.urls import url
from rest_framework import routers
from rest_framework_simplejwt.views import TokenRefreshView

from api.views import PostViewSet, TagViewSet, TagSnapshotViewSet, AttributeViewSet, TokenObtainPairViewWithThrottle

router = routers.SimpleRouter()
router.register(r'posts', PostViewSet)
router.register(r'tags', TagViewSet)
router.register(r'tag_snapshots', TagSnapshotViewSet)
router.register(r'attributes', AttributeViewSet)
urlpatterns = [
                  url(r'^token/$', TokenObtainPairViewWithThrottle.as_view(), name='token_obtain_pair'),
                  url(r'^token/refresh/$', TokenRefreshView.as_view(), name='token_refresh')
              ] + router.urls
