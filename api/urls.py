from django.conf.urls import url
from django.urls import include
from rest_framework import routers
from rest_framework_simplejwt.views import TokenRefreshView

from api.views import PostViewSet, TagViewSet, TagSnapshotViewSet, AttributeViewSet, TokenObtainPairViewWithThrottle

router = routers.DefaultRouter()
router.register(r'posts', PostViewSet)
router.register(r'tags', TagViewSet)
router.register(r'tag_snapshots', TagSnapshotViewSet)
router.register(r'attributes', AttributeViewSet)
urlpatterns = [
                  url(r'^token/$', TokenObtainPairViewWithThrottle.as_view(), name='token_obtain_pair'),
                  url(r'^token/refresh/$', TokenRefreshView.as_view(), name='token_refresh')
              ] + router.urls + [
                  url(r'^api-auth/', include('rest_framework.urls')),
              ]
