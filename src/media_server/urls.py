from django.urls import path

from .views import ServeView, UploadView, HealthView

urlpatterns = [
    path('health/', HealthView.as_view(), name='health'),
    path('upload/', UploadView.as_view(), name='upload'),
    path('serve/<path:file_path>', ServeView.as_view(), name='serve'),
]
