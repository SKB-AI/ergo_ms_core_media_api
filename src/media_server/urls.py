from django.urls import path

from .views import ServeView, UploadView, HealthView
from .views_internal import (
    InternalDeleteView,
    InternalMetaView,
    InternalReadView,
    InternalWriteView,
)

urlpatterns = [
    path('health/', HealthView.as_view(), name='health'),
    path('upload/', UploadView.as_view(), name='upload'),
    path('serve/<path:file_path>', ServeView.as_view(), name='serve'),
    path('internal/meta/<path:file_path>', InternalMetaView.as_view(), name='internal_meta'),
    path('internal/read/<path:file_path>', InternalReadView.as_view(), name='internal_read'),
    path('internal/write/<path:file_path>', InternalWriteView.as_view(), name='internal_write'),
    path('internal/delete/<path:file_path>', InternalDeleteView.as_view(), name='internal_delete'),
]
