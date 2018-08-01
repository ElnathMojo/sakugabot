from rest_framework import routers

from api.views import PostViewSet, TagViewSet, TagSnapshotViewSet, AttributeViewSet

router = routers.SimpleRouter()
router.register(r'posts', PostViewSet)
router.register(r'tags', TagViewSet)
router.register(r'tag_snapshots', TagSnapshotViewSet)
router.register(r'attributes', AttributeViewSet)
urlpatterns = router.urls
