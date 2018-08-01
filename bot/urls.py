from bot import views
from django.urls import path

urlpatterns = [
    path('log/', views.ShowLog.as_view(), name='log'),
    path('test/', views.test, name='test')
]
