from bot import views
from django.urls import path

app_name = 'bot'

urlpatterns = [
    path('log/', views.ShowLog.as_view(), name='log'),
    path('test/', views.test, name='test')
]
