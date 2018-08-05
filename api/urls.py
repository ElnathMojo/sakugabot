from django.conf.urls import url
from django.contrib.auth.views import LoginView, LogoutView
from rest_framework import routers
from rest_framework_simplejwt.views import TokenRefreshView

from api.views import PostViewSet, TagViewSet, TagSnapshotViewSet, AttributeViewSet, TokenObtainPairViewWithThrottle
from sakugabot.decorators import login_wrapper

app_name = 'api'

login = login_wrapper(LoginView.as_view(template_name='rest_framework/login.html'))
login_kwargs = {}
logout = LogoutView.as_view()

routers.DefaultRouter.APIRootView.__doc__ = "Sakugabot API Root"
router = routers.DefaultRouter()
router.register(r'posts', PostViewSet)
router.register(r'tags', TagViewSet)
router.register(r'tag_snapshots', TagSnapshotViewSet)
router.register(r'attributes', AttributeViewSet)
urlpatterns = [
                  url(r'^token/$', TokenObtainPairViewWithThrottle.as_view(), name='token_obtain_pair'),
                  url(r'^token/refresh/$', TokenRefreshView.as_view(), name='token_refresh')
              ] + router.urls + [
                  url(r'^login/$', login, name='login'),
                  url(r'^logout/$', logout, name='logout')
              ]
