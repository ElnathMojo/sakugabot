from django.urls import path

from bot import views

app_name = 'bot'

urlpatterns = [
    path('log/', views.ShowLog.as_view(), name='log'),
    path('test/', views.test, name='test'),
    path('scan/', views.ScanQRCode.as_view(), name='scan')
]
